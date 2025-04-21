import wave
from pathlib import Path
from types import TracebackType
from typing import Literal, Self

from synchro.audio.frame_container import FrameContainer
from synchro.config.schemas import OutputFileNodeSchema
from synchro.graph.nodes.outputs.abstract_output_node import AbstractOutputNode


class FileOutputNode(AbstractOutputNode):
    def __init__(
        self,
        config: OutputFileNodeSchema,
        working_dir: Path | None = None,
    ) -> None:
        super().__init__(config.name)
        self._config = config
        self._wave_file: wave.Wave_write | None = None
        self._working_dir = working_dir
        path = self._config.path
        if "$WORKING_DIR" in str(path):
            path = Path(str(path).replace("$WORKING_DIR", str(self._working_dir)))
        self._file_path = Path(path)
        self._file_path.touch(exist_ok=True)

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
            self._wave_file = wave.open(str(self._file_path), "w")
            self._wave_file.setnchannels(1)
            self._wave_file.setsampwidth(data.audio_format.sample_size)
            self._wave_file.setframerate(data.rate)
        self._wave_file.writeframes(data.frame_data)
