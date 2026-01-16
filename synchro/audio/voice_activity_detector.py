from enum import Enum

import numpy as np

from synchro.audio.frame_container import FrameContainer
from synchro.config.commons import StreamConfig


class VoiceActivityDetectorResult(str, Enum):
    SPEECH = "speech"
    NON_SPEECH = "non_speech"
    NOT_ENOUGH_INFO = "not_enough_info"


class VoiceActivityDetector:
    def __init__(
        self,
        config: StreamConfig,
        buffer_size_sec: float = 0.3,
        threshold: int = 1000,
    ) -> None:
        self._vad = None
        self._buffer_size_sec = buffer_size_sec
        self._buffer: FrameContainer = FrameContainer.from_config(config)
        self._threshold = threshold

    def detect_voice(self, audio_data: FrameContainer) -> VoiceActivityDetectorResult:
        if self._buffer.rate != audio_data.rate:
            raise ValueError("Audio data rate does not match the buffer")
        if self._buffer.audio_format != audio_data.audio_format:
            raise ValueError("Audio data format does not match the buffer")

        self._buffer.append_inp(audio_data)
        if self._buffer.length_secs < self._buffer_size_sec:
            return VoiceActivityDetectorResult.NOT_ENOUGH_INFO
        self._buffer = self._buffer.get_end_seconds(self._buffer_size_sec)
        joined_buffer = np.frombuffer(self._buffer.frame_data, np.int16)
        has_speech = np.mean(np.abs(joined_buffer)) > self._threshold
        return (
            VoiceActivityDetectorResult.SPEECH
            if has_speech
            else VoiceActivityDetectorResult.NON_SPEECH
        )
