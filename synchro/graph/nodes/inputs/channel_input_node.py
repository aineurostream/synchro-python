from types import TracebackType
from typing import Literal, Self, cast

import numpy as np
import sounddevice as sd

from synchro.audio.frame_container import FrameContainer
from synchro.config.audio_format import DEFAULT_AUDIO_FORMAT
from synchro.config.commons import StreamConfig
from synchro.config.schemas import InputChannelStreamerNodeSchema
from synchro.graph.nodes.inputs.abstract_input_node import AbstractInputNode


class ChannelInputNode(AbstractInputNode):
    def __init__(
        self,
        config: InputChannelStreamerNodeSchema,
    ) -> None:
        super().__init__(config.name)
        self._config = config
        self._stream: sd.InputStream | None = None
        self._incoming_buffer: FrameContainer | None = None

    def __enter__(self) -> Self:
        def callback(
            input_data: np.ndarray,
            _frames: int,
            _time: int,
            status: str | None,
        ) -> None:
            if status:
                self._logger.error("Error in audio stream: %s", status)
            if self._incoming_buffer is None:
                raise RuntimeError("Incoming buffer is not initialized")
            chunk = cast(bytes, input_data.tobytes())
            self._incoming_buffer.append_bytes_inp(chunk)

        device_info = sd.query_devices(self._config.device, "input")
        sample_rate = device_info["default_samplerate"]
        self._incoming_buffer = FrameContainer.from_config(
            StreamConfig(audio_format=DEFAULT_AUDIO_FORMAT, rate=sample_rate),
        )
        self._stream = sd.InputStream(
            device=self._config.device,
            channels=self._config.channel,
            dtype=DEFAULT_AUDIO_FORMAT.numpy_format,
            samplerate=sample_rate,
            callback=callback,
        )
        self._stream.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> Literal[False]:
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._incoming_buffer = None

        return False

    def get_data(self) -> FrameContainer | None:
        if not self._stream:
            raise RuntimeError("Audio stream is not open")
        if self._incoming_buffer is None:
            raise RuntimeError("Incoming buffer is not initialized")
        read_bytes = self._incoming_buffer
        self._incoming_buffer = self._incoming_buffer.to_empty()
        return read_bytes
