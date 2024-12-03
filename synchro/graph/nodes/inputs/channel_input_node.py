from types import TracebackType
from typing import Literal, Self, cast

import pyaudio
from pydub import AudioSegment, effects

from synchro.audio.audio_device_manager import AudioDeviceManager
from synchro.audio.voice_activity_detector import (
    VoiceActivityDetector,
    VoiceActivityDetectorResult,
)
from synchro.config.commons import (
    MIN_BUFFER_SIZE_SEC, PREFERRED_BUFFER_SIZE_SEC, MIN_WORKING_STEP_LENGTH_SECS, MIN_STEP_LENGTH_SECS
)
from synchro.config.schemas import InputChannelStreamerNodeSchema
from synchro.graph.graph_frame_container import GraphFrameContainer
from synchro.graph.nodes.inputs.abstract_input_node import AbstractInputNode


class ChannelInputNode(AbstractInputNode):
    def __init__(
        self,
        config: InputChannelStreamerNodeSchema,
        manager: AudioDeviceManager,
    ) -> None:
        super().__init__(config.name)
        self._config = config
        self._manager = manager
        self._vad = VoiceActivityDetector(
            sample_size_bytes=self._config.stream.audio_format.sample_size,
            sample_rate=config.stream.rate,
            min_buffer_size_sec=MIN_BUFFER_SIZE_SEC,
            shrink_buffer_size_sec=PREFERRED_BUFFER_SIZE_SEC,
        )
        self._stream: pyaudio.Stream | None = None

    def __enter__(self) -> Self:
        self._stream = self._manager.context.open(
            format=self._config.stream.audio_format.pyaudio_format,
            channels=self._config.channel,
            rate=self._config.stream.rate,
            input=True,
            input_device_index=self._config.device,
            frames_per_buffer=self._config.chunk_size,
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

    def get_data(self) -> GraphFrameContainer:
        return GraphFrameContainer.from_config(
            self.name,
            self._config.stream,
            self._read_speech_frames(),
        )

    def _read_speech_frames(self) -> bytes:
        if not self._stream:
            raise RuntimeError("Audio stream is not open")

        desired_size = self._config.stream.rate
        read_bytes = self._stream.read(desired_size)
        read_bytes = self._normalize_audio(read_bytes)
        voice_result = self._vad.detect_voice(read_bytes)
        if voice_result == VoiceActivityDetectorResult.SPEECH:
            self._logger.debug("Detected speech: %d bytes", len(read_bytes))
            return read_bytes
        return b""

    def _normalize_audio(self, audio: bytes) -> bytes:
        audio_segment = AudioSegment(
            audio,
            frame_rate=self._config.stream.rate,
            sample_width=self._config.stream.audio_format.sample_size,
            channels=1,
        )
        audio_segment = effects.normalize(audio_segment, headroom=7.5)

        return cast(bytes, audio_segment.raw_data)
