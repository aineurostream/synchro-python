import wave
from types import TracebackType
from typing import Literal, Self

from synchro.config.commons import StreamConfig
from synchro.config.schemas import OutputFileNodeSchema
from synchro.graph.graph_frame_container import GraphFrameContainer
from synchro.graph.nodes.outputs.abstract_output_node import AbstractOutputNode


class FileOutputNode(AbstractOutputNode):
    def __init__(
        self,
        config: OutputFileNodeSchema,
    ) -> None:
        super().__init__(config.name)
        self._config = config
        self._wave_file: wave.Wave_write | None = None

    def __enter__(self) -> Self:
        self._wave_file = wave.open(str(self._config.path), "w")
        self._wave_file.setnchannels(1)
        self._wave_file.setsampwidth(self._config.stream.audio_format.sample_size)
        self._wave_file.setframerate(self._config.stream.rate)

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> Literal[False]:
        if self._wave_file is not None:
            self._wave_file.close()
            self._wave_file = None

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

    def put_data(self, frames: list[GraphFrameContainer]) -> None:
        if len(frames) != 1:
            raise ValueError("Expected one frame container")

        if self._wave_file is None:
            raise RuntimeError("Audio stream is not open")

        self._wave_file.writeframes(frames[0].frame_data)
