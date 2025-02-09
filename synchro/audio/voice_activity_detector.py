from enum import Enum

import numpy as np

from synchro.audio.frame_container import FrameContainer

DEFAULT_MINIMAL_EDGE = 1000


class VoiceActivityDetectorResult(str, Enum):
    SPEECH = "speech"
    NON_SPEECH = "non_speech"
    NOT_ENOUGH_INFO = "not_enough_info"


class VoiceActivityDetector:
    def __init__(
        self,
        min_buffer_size_sec: float = 0.05,
        shrink_buffer_size_sec: float = 0.3,
    ) -> None:
        self._vad = None
        self._min_buffer_size_sec = min_buffer_size_sec
        self._shrink_buffer_size_sec = shrink_buffer_size_sec
        self._buffer: list[bytes] = []
        self._sample_size_bytes = 2
        self._sample_rate = 0

    def detect_voice(self, audio_data: FrameContainer) -> VoiceActivityDetectorResult:
        self._buffer.append(audio_data.frame_data)

        if self._sample_rate == 0:
            self._sample_size_bytes = audio_data.audio_format.sample_size
            self._sample_rate = audio_data.rate

        if self.stored_buffer_duration_sec < self._min_buffer_size_sec:
            return VoiceActivityDetectorResult.NOT_ENOUGH_INFO

        self._shrink_buffer()

        joined_buffer = np.frombuffer(b"".join(self._buffer), np.int16)

        has_speech = np.any(abs(joined_buffer) > DEFAULT_MINIMAL_EDGE)
        return (
            VoiceActivityDetectorResult.SPEECH
            if has_speech
            else VoiceActivityDetectorResult.NON_SPEECH
        )

    @property
    def stored_buffer_duration_sec(self) -> float:
        return sum(self._sample_duration_sec(part) for part in self._buffer)

    def _sample_duration_sec(self, sample: bytes) -> float:
        return len(sample) / self._sample_size_bytes / self._sample_rate

    def _shrink_buffer(self) -> None:
        buffer_duration_sec = self.stored_buffer_duration_sec

        if buffer_duration_sec < self._shrink_buffer_size_sec:
            return

        while buffer_duration_sec > self._shrink_buffer_size_sec:
            if not self._buffer:
                return

            first_element = self._buffer[0]
            first_element_duration_sec = self._sample_duration_sec(first_element)
            left_after_deletion_sec = buffer_duration_sec - first_element_duration_sec

            if left_after_deletion_sec > self._min_buffer_size_sec:
                self._buffer.pop(0)
                buffer_duration_sec -= left_after_deletion_sec
            else:
                break
