from enum import Enum

import webrtcvad


class VoiceActivityDetectorResult(str, Enum):
    SPEECH = "speech"
    NON_SPEECH = "non_speech"
    NOT_ENOUGH_INFO = "not_enough_info"


class VoiceActivityDetector:
    def __init__(
        self,
        sample_size_bytes: int = 2,
        sample_rate: int = 16000,
        min_buffer_size_sec: float = 0.05,
        shrink_buffer_size_sec: float = 0.2,
    ) -> None:
        self._vad = webrtcvad.Vad()
        self._sample_size_bytes = sample_size_bytes
        self._sample_rate = sample_rate
        self._min_buffer_size_sec = min_buffer_size_sec
        self._shrink_buffer_size_sec = shrink_buffer_size_sec
        self._buffer: list[bytes] = []

    def detect_voice(self, audio_data: bytes) -> VoiceActivityDetectorResult:
        self._buffer.append(audio_data)

        if self.stored_buffer_duration_sec < self._min_buffer_size_sec:
            return VoiceActivityDetectorResult.NOT_ENOUGH_INFO

        self._shrink_buffer()

        result = self._vad.is_speech(
            audio_data,
            sample_rate=self._sample_rate,
        )

        return (
            VoiceActivityDetectorResult.SPEECH
            if result
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
            first_element = self._buffer[0]
            first_element_duration_sec = self._sample_duration_sec(first_element)
            left_after_deletion_sec = buffer_duration_sec - first_element_duration_sec

            if left_after_deletion_sec > self._min_buffer_size_sec:
                self._buffer.pop(0)
                buffer_duration_sec -= left_after_deletion_sec
            else:
                break
