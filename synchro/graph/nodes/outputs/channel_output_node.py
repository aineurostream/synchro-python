import logging
import time
import threading
from types import TracebackType
from typing import Literal, Self

import numpy as np
import sounddevice as sd

from synchro.audio.frame_container import FrameContainer
from synchro.config.audio_format import DEFAULT_AUDIO_FORMAT
from synchro.config.schemas import OutputChannelStreamerNodeSchema
from synchro.graph.nodes.outputs.abstract_output_node import AbstractOutputNode

logger = logging.getLogger(__name__)


PREFILL_SECONDS = 2
JACK_ENABLED = False
JACK_DEVICE = "jack"


class ChannelOutputNode(AbstractOutputNode):
    """
    Узел вывода на устройство. 
    
    Ключевые особенности:
      - Буфер потокобезопасен (lock),
      - Конвертация байтов ↔ numpy строго под dtype стрима,
      - Моно-данные дублируются во все доступные (или 2) канала вывода.
    """

    def __init__(
        self,
        config: OutputChannelStreamerNodeSchema,
        output_interval_secs: float = 0.016,
    ) -> None:
        super().__init__(config.name)
        self._config = config
        self._output_interval_secs = output_interval_secs
        self._sample_rate = 0
        self._stream: sd.OutputStream | None = None
        self._last_time_emit = 0.0
        self._out_buffer = b""
        self._lock = threading.Lock()

    def __enter__(self) -> Self:
        def callback(
            out_data: np.ndarray, 
            frames: int, 
            _time: int, 
            status: str | None
        ) -> None:
            if status:
                logger.error("Error in audio stream: %s", status)

            # Достаём накопленные байты атомарно
            with self._lock:
                buf = self._out_buffer
                self._out_buffer = b""

            dtype = DEFAULT_AUDIO_FORMAT.numpy_format  # должен совпадать с dtype стрима!
            samples = np.frombuffer(buf, dtype=dtype)

            # Мы считаем, что приходят МОНО-данные. Дублируем во все выходные каналы.
            # out_data.shape = (frames, out_channels)
            out_channels = 1 if out_data.ndim == 1 else out_data.shape[1]
            available = min(frames, samples.size)

            if available > 0:
                # Заполняем каждую колонку одинаковыми моно-сэмплами
                for ch in range(out_channels):
                    out_data[:available, ch] = samples[:available]
                if available < frames:
                    out_data[available:, :] = 0
            else:
                out_data[:, :] = 0

        device = JACK_DEVICE if JACK_ENABLED else self._config.device
        device_info = sd.query_devices(device, "output")
        self._sample_rate = int(device_info["default_samplerate"])

        # Кол-во каналов вывода — не более 2 (стерео) и не более max_device_channels
        max_dev_ch = int(device_info.get("max_output_channels", 2))
        out_channels = min(max(2, 1), max_dev_ch)  # минимум стерео, если устройство позволяет

        self._stream = sd.OutputStream(
            device=device,
            channels=out_channels,
            samplerate=self._sample_rate,
            dtype=DEFAULT_AUDIO_FORMAT.numpy_format,  # например, np.int16
            callback=callback,
        )
        self._stream.start()

        # Предзаполнение нулями, чтобы callback имел запас на первом цикле
        prefill_frames = int(self._sample_rate * PREFILL_SECONDS)
        with self._lock:
            self._out_buffer += np.zeros((prefill_frames,), dtype=DEFAULT_AUDIO_FORMAT.numpy_format).tobytes()

        return self

    def _cleanup(self):
        logger.info("Cleanup output node")
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            finally:
                self._stream = None
        return False

    def __exit__(self, exc_type, exc_val, exc_tb) -> Literal[False]:
        self._cleanup()

    def __del__(self):
        self._cleanup()

    def put_data(self, _source: str, data: FrameContainer) -> None:
        """
        Принимаем моно PCM-данные в формате DEFAULT_AUDIO_FORMAT.
        Если формат/частота отличаются — лучше конвертировать на предыдущем шаге
        (через FormatValidatorNode и/или ResampleNode).
        """
        if self._stream is None:
            raise RuntimeError("Audio stream is not open")

        if data.rate != self._sample_rate:
            logger.warning("Data rate is %d, expected device rate %d", data.rate, self._sample_rate)

        # Копим байты атомарно (callback читает этот буфер)
        with self._lock:
            self._out_buffer += data.frame_data

        # Мониторим тайминг через monotonic — устойчиво к NTP/сдвигам
        current_emit_time = time.monotonic()
        if self._last_time_emit > 0:
            time_diff = current_emit_time - self._last_time_emit
            if time_diff > data.length_secs:
                logger.warning(
                    "Time diff is %.3f while expected %.3f",
                    time_diff,
                    data.length_secs,
                )
        self._last_time_emit = current_emit_time
