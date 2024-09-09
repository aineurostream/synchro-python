import wave
from types import TracebackType
from typing import Literal, Self

from synchro.audio.frame_container import FrameContainer
from synchro.config.commons import StreamConfig
from synchro.config.schemas import InputFileStreamerNodeSchema
from synchro.graph.nodes.inputs.abstract_input_node import AbstractInputNode


class FileInputNode(AbstractInputNode):
    def __init__(
        self,
        config: InputFileStreamerNodeSchema,
    ) -> None:
        super().__init__(config.name)
        self._config = config
        self._wavefile_data: bytes | None = None

    def __enter__(self) -> Self:
        wavefile = wave.open(str(self._config.path), "r")

        length = wavefile.getnframes()
        self._wavefile_data = wavefile.readframes(length)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> Literal[False]:
        self._wavefile_data = None
        return False

    def initialize_edges(
        self,
        inputs: list[StreamConfig],
        outputs: list[StreamConfig],
    ) -> None:
        self.check_inputs_count(inputs, 0)
        self.check_has_outputs(outputs)

    def predict_config(
        self,
        _inputs: list[StreamConfig],
    ) -> StreamConfig:
        return self._config.stream

    def get_data(self) -> FrameContainer:
        if self._wavefile_data is None:
            return FrameContainer.from_config(
                self._config.stream,
                b"",
            )

        data_to_send = self._wavefile_data

        if not self._config.looping:
            self._wavefile_data = None

        return FrameContainer.from_config(
            self._config.stream,
            data_to_send,
        )
