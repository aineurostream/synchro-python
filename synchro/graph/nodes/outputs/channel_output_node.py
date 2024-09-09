from types import TracebackType
from typing import Literal, Self

import pyaudio

from synchro.audio.audio_device_manager import AudioDeviceManager
from synchro.audio.frame_container import FrameContainer
from synchro.config.commons import StreamConfig
from synchro.config.schemas import OutputChannelStreamerNodeSchema
from synchro.graph.nodes.outputs.abstract_output_node import AbstractOutputNode


class ChannelOutputNode(AbstractOutputNode):
    def __init__(
        self,
        config: OutputChannelStreamerNodeSchema,
        manager: AudioDeviceManager,
    ) -> None:
        super().__init__(config.name)
        self._config = config
        self._manager = manager
        self._stream: pyaudio.Stream | None = None

    def __enter__(self) -> Self:
        self._stream = self._manager.context.open(
            format=self._config.stream.audio_format.pyaudio_format,
            channels=self._config.channel,
            rate=self._config.stream.rate,
            output=True,
            output_device_index=self._config.device,
        )

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> Literal[False]:
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()

        return False

    def initialize_edges(
        self,
        inputs: list[StreamConfig],
        outputs: list[StreamConfig],
    ) -> None:
        self.check_inputs_count(inputs, 1)
        self.check_outputs_count(outputs, 0)

        if inputs[0].audio_format != self._config.stream.audio_format:
            raise ValueError(
                f"Node {self} has AF {inputs[0].audio_format} "
                f"but expected {self._config.stream.audio_format}",
            )

        if inputs[0].rate != self._config.stream.rate:
            raise ValueError(
                f"Node {self} has rate {inputs[0].rate} "
                f"but expected {self._config.stream.rate}",
            )

    def predict_config(
        self,
        _inputs: list[StreamConfig],
    ) -> StreamConfig:
        return self._config.stream

    def put_data(self, frames: list[FrameContainer]) -> None:
        if len(frames) != 1:
            raise ValueError("Expected one frame container")

        if self._stream is None:
            raise RuntimeError("Audio stream is not open")

        self._stream.write(frames[0].frame_data)
