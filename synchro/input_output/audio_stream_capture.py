import logging
from types import TracebackType
from typing import Literal, Self

import pyaudio

from synchro.input_output.audio_device_manager import AudioDeviceManager
from synchro.input_output.schemas import InputAudioStreamConfig
from synchro.input_output.voice_activity_detector import (
    VoiceActivityDetector,
    VoiceActivityDetectorResult,
)

logger = logging.getLogger(__name__)

SAMPLE_SIZE_BYTES_INT_16 = 2
PREFERRED_BUFFER_SIZE_SEC = 0.2
MIN_BUFFER_SIZE_SEC = 0.03


class AudioStreamInput:
    def __init__(
        self,
        manager: AudioDeviceManager,
        config: InputAudioStreamConfig,
    ) -> None:
        if config.audio_format != pyaudio.paInt16:
            raise ValueError("Only paInt16 audio format is supported")

        self._config = config
        self._manager = manager
        self._vad = VoiceActivityDetector(
            sample_size_bytes=SAMPLE_SIZE_BYTES_INT_16,
            sample_rate=config.rate,
            min_buffer_size_sec=MIN_BUFFER_SIZE_SEC,
            shrink_buffer_size_sec=PREFERRED_BUFFER_SIZE_SEC,
        )
        self._stream: pyaudio.Stream | None = None

    def __enter__(self) -> Self:
        self._stream = self._manager.context.open(
            format=self._config.audio_format,
            channels=self._config.channels,
            rate=self._config.rate,
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

    def get_speech_frames(self) -> bytes:
        if not self._stream:
            raise RuntimeError("Audio stream is not open")

        read_bytes = self._stream.read(
            self._config.chunk_size,
            exception_on_overflow=False,
        )

        voice_result = self._vad.detect_voice(read_bytes)
        if voice_result == VoiceActivityDetectorResult.SPEECH:
            logger.debug("Detected speech")
            return read_bytes

        logger.debug("No speech detected")
        return b""
