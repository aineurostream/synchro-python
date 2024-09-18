import wave
from types import TracebackType
from typing import Literal, Self

from synchro.config.commons import MIN_WORKING_STEP_LENGTH_SECS, StreamConfig
from synchro.config.schemas import InputFileStreamerNodeSchema
from synchro.graph.graph_frame_container import GraphFrameContainer
from synchro.graph.nodes.inputs.abstract_input_node import AbstractInputNode


class FileInputNode(AbstractInputNode):
    def __init__(
        self,
        config: InputFileStreamerNodeSchema,
    ) -> None:
        super().__init__(config.name)
        self._config = config
        self._wavefile_data: bytes | None = None
        self._wavefile_index = 0
        self._delay_completed = False

    def __enter__(self) -> Self:
        wavefile = wave.open(str(self._config.path), "r")

        length = wavefile.getnframes()
        self._wavefile_data = wavefile.readframes(length)
        self._wavefile_index = 0
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

    def get_data(self) -> GraphFrameContainer:
        if self._wavefile_data is None:
            return GraphFrameContainer.from_config(
                self.name,
                self._config.stream,
                b"",
            )

        if not self._delay_completed and self._config.delay_ms > 0:
            self._delay_completed = True
            delay_seconds = self._config.delay_ms / 1000
            delay_bytes = int(
                delay_seconds
                * self._config.stream.rate
                * self._config.stream.audio_format.sample_size,
            )
            return GraphFrameContainer.from_config(
                self.name,
                self._config.stream,
                b"\x00" * delay_bytes,
            )

        bytes_per_batch = int(
            MIN_WORKING_STEP_LENGTH_SECS
            * self._config.stream.rate
            * self._config.stream.audio_format.sample_size,
        )

        data_to_send = self._wavefile_data[
            self._wavefile_index : self._wavefile_index + bytes_per_batch
        ]
        self._wavefile_index += len(data_to_send)

        if len(data_to_send) < bytes_per_batch and self._config.looping:
            bytes_left = bytes_per_batch - len(data_to_send)
            data_to_send += self._wavefile_data[
                self._wavefile_index : self._wavefile_index + bytes_left
            ]
            self._wavefile_index = bytes_left
        elif self._wavefile_index >= len(self._wavefile_data):
            self._wavefile_index = 0
            if not self._config.looping:
                self._wavefile_data = None

        return GraphFrameContainer.from_config(
            self.name,
            self._config.stream,
            data_to_send,
        )
