import wave
from types import TracebackType
from typing import Literal, Self

from synchro.audio.frame_container import FrameContainer
from synchro.config.schemas import OutputFileNodeSchema
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

    def put_data(self, _source: str, data: FrameContainer) -> None:
        if self._wave_file is None:
            self._wave_file = wave.open(str(self._config.path), "w")
            self._wave_file.setnchannels(1)
            self._wave_file.setsampwidth(data.audio_format.sample_size)
            self._wave_file.setframerate(data.rate)
        self._wave_file.writeframes(data.frame_data)
