from types import TracebackType
from typing import Literal, Self, cast

import numpy as np
import sounddevice as sd

from synchro.config.schemas import InputChannelStreamerNodeSchema
from synchro.graph.graph_frame_container import GraphFrameContainer
from synchro.graph.nodes.inputs.abstract_input_node import AbstractInputNode


class ChannelInputNode(AbstractInputNode):
    def __init__(
        self,
        config: InputChannelStreamerNodeSchema,
    ) -> None:
        super().__init__(config.name)
        self._config = config
        self._stream: sd.InputStream | None = None
        self._incoming_buffer = b""

    def __enter__(self) -> Self:
        def callback(
            input_data: np.ndarray,
            _frames: int,
            _time: int,
            status: str | None,
        ) -> None:
            if status:
                self._logger.error("Error in audio stream: %s", status)

            chunk = cast(bytes, input_data.tobytes())
            self._incoming_buffer += chunk

        device_info = sd.query_devices(self._config.device, "input")
        sample_rate = device_info["default_samplerate"]

        if sample_rate != self._config.stream.rate:
            self._logger.warning(
                "Input device sample rate is %d, while expected %d",
                sample_rate,
                self._config.stream.rate,
            )

        self._stream = sd.InputStream(
            device=self._config.device,
            channels=self._config.channel,
            dtype=self._config.stream.audio_format.numpy_format,
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

        return False

    def get_data(self) -> GraphFrameContainer:
        return GraphFrameContainer.from_config(
            self.name,
            self._config.stream,
            self._read_speech_frames(),
        )

    def _read_speech_frames(self) -> bytes:
        if not self._stream:
            raise RuntimeError("Audio stream is not open")

        read_bytes = self._incoming_buffer
        self._incoming_buffer = b""
        return read_bytes
