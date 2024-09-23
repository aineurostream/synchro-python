import time
import wave
from types import TracebackType
from typing import Literal, Self

from synchro.config.commons import StreamConfig
from synchro.config.schemas import InputFileStreamerNodeSchema
from synchro.graph.graph_frame_container import GraphFrameContainer
from synchro.graph.nodes.inputs.abstract_input_node import AbstractInputNode

BYTES_IN_INT16 = 2


class FileInputNode(AbstractInputNode):
    def __init__(
        self,
        config: InputFileStreamerNodeSchema,
    ) -> None:
        super().__init__(config.name)
        self._config = config
        self._wavefile_data: bytes | None = None
        self._wavefile_index = 0
        self._delay_left = self._config.delay_ms
        self._last_query = time.time()

    def __enter__(self) -> Self:
        wavefile = wave.open(str(self._config.path), "r")

        if wavefile.getnchannels() != 1:
            raise ValueError("Only mono files are supported")

        if wavefile.getsampwidth() != BYTES_IN_INT16:
            raise ValueError("Only 16-bit audio files are supported")

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
            )

        time_passed_ms = int((time.time() - self._last_query) * 1000)

        if self._delay_left > 0:
            delay_duration_ms = min(self._delay_left, time_passed_ms)
            delay_samples = int(delay_duration_ms * self._config.stream.rate // 1000)
            delay_bytes = delay_samples * self._config.stream.audio_format.sample_size
            self._delay_left -= delay_duration_ms
            self._last_query = time.time()
            return GraphFrameContainer.from_config(
                self.name,
                self._config.stream,
                b"\x00" * delay_bytes,
            )

        time_passed_samples = int(time_passed_ms * self._config.stream.rate // 1000)
        time_passed_bytes = (
            time_passed_samples * self._config.stream.audio_format.sample_size
        )
        self._last_query = time.time()

        data_to_send = self._wavefile_data[
            self._wavefile_index : self._wavefile_index + time_passed_bytes
        ]
        self._wavefile_index += time_passed_bytes

        not_enough_data = len(data_to_send) < time_passed_bytes
        if not_enough_data and self._config.looping:
            bytes_left = time_passed_bytes - len(data_to_send)
            data_to_send += self._wavefile_data[0:bytes_left]
            self._wavefile_index = bytes_left
        elif not_enough_data:
            self._wavefile_data = None
            return GraphFrameContainer.from_config(
                self.name,
                self._config.stream,
            )

        return GraphFrameContainer.from_config(
            self.name,
            self._config.stream,
            data_to_send,
        )
