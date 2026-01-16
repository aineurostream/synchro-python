import logging
import threading
import sounddevice as sd
import numpy as np

from typing import Literal, Self, cast
from types import TracebackType

from synchro.audio.frame_container import FrameContainer
from synchro.config.schemas import InputChannelStreamerNodeSchema
from synchro.config.commons import StreamConfig
from synchro.graph.nodes.inputs.abstract_input_node import AbstractInputNode
from synchro.config.audio_format import DEFAULT_AUDIO_FORMAT

logger = logging.getLogger(__name__)

JACK_ENABLED = False
JACK_DEVICE = "jack"


class ChannelInputNode(AbstractInputNode):
    """
    Узел живого входа. Делает:
      - корректную выборку канала при JACK,
      - микширование в моно при многоканале (без JACK),
      - потокобезопасное накопление байтов в буфере,
      - строгое соответствие dtype <-> FrameContainer.audio_format.
    """

    def __init__(self, config: InputChannelStreamerNodeSchema) -> None:
        super().__init__(config.name)
        self._config = config
        self._stream: sd.InputStream | None = None
        self._incoming_buffer: FrameContainer | None = None
        self._lock = threading.Lock()

    def __enter__(self) -> Self:
        def callback(input_data: np.ndarray, _frames: int, _time: int, status: str | None) -> None:
            if status:
                logger.error("Error in audio stream: %s", status)
            if self._incoming_buffer is None:
                return

            # Преобразуем поступивший блок к моно-буферу.
            if JACK_ENABLED:
                # В режиме JACK берём канал из self._config.channel (индекс начинается с 1).
                chan_idx = max(0, self._config.channel - 1)
                if input_data.ndim == 1:
                    mono = input_data.astype(input_data.dtype)
                else:
                    mono = input_data[:, chan_idx].astype(input_data.dtype)
            else:
                # Без JACK: если пришло N каналов — усредняем в моно.
                if input_data.ndim == 2 and input_data.shape[1] > 1:
                    mono = np.mean(input_data, axis=1).astype(input_data.dtype)
                else:
                    mono = input_data.astype(input_data.dtype)

            payload = cast(bytes, mono.tobytes())
            with self._lock:
                self._incoming_buffer.append_bytes_inp(payload)

        device = JACK_DEVICE if JACK_ENABLED else self._config.device
        device_info = sd.query_devices(device, "input")
        sample_rate = int(device_info["default_samplerate"])

        # ВНИМАНИЕ: dtype в стриме должен совпадать с DEFAULT_AUDIO_FORMAT.numpy_format!
        dtype = DEFAULT_AUDIO_FORMAT.numpy_format  # например, np.int16
        channels = self._config.channel if JACK_ENABLED else max(1, self._config.channel)

        self._incoming_buffer = FrameContainer.from_config(
            StreamConfig(audio_format=DEFAULT_AUDIO_FORMAT, rate=sample_rate),
        )
        self._stream = sd.InputStream(
            device=device,
            channels=channels,
            dtype=dtype,
            samplerate=sample_rate,
            callback=callback,
        )
        self._stream.start()
        return self

    def _cleanup(self):
        logger.info("Cleanup input node")
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            finally:
                self._stream = None
                self._incoming_buffer = None
        return False

    def __exit__(self, exc_type, exc_val, exc_tb) -> Literal[False]:
        self._cleanup()

    def __del__(self):
        self._cleanup()

    def get_data(self) -> FrameContainer | None:
        """
        Забираем накопившийся блок как моно PCM с dtype, согласованным с DEFAULT_AUDIO_FORMAT.
        """
        if not self._stream:
            raise RuntimeError("Audio stream is not open")
        if self._incoming_buffer is None:
            raise RuntimeError("Incoming buffer is not initialized")
        with self._lock:
            read_bytes = self._incoming_buffer
            self._incoming_buffer = self._incoming_buffer.to_empty()
        return read_bytes
