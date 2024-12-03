import wave
from types import TracebackType
from typing import Literal, Self

from synchro.audio.voice_activity_detector import (
    VoiceActivityDetector,
    VoiceActivityDetectorResult,
)
from synchro.config.commons import MIN_BUFFER_SIZE_SEC, PREFERRED_BUFFER_SIZE_SEC
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
        self._vad = VoiceActivityDetector(
            sample_size_bytes=self._config.stream.audio_format.sample_size,
            sample_rate=config.stream.rate,
            min_buffer_size_sec=MIN_BUFFER_SIZE_SEC,
            shrink_buffer_size_sec=PREFERRED_BUFFER_SIZE_SEC,
        )

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

    def put_data(self, frames: list[GraphFrameContainer]) -> None:
        if len(frames) != 1:
            raise ValueError("Expected one frame container")

        if self._wave_file is None:
            raise RuntimeError("Audio stream is not open")

        voice_result = self._vad.detect_voice(frames[0].frame_data)
        if voice_result == VoiceActivityDetectorResult.SPEECH:
            self._wave_file.writeframes(frames[0].frame_data)
