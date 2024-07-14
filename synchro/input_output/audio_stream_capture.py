from types import TracebackType
from typing import Literal, Self

import pyaudio

from synchro.input_output.audio_device_manager import AudioDeviceManager
from synchro.input_output.schemas import InputAudioStreamConfig


class AudioStreamInput:
    def __init__(
        self,
        manager: AudioDeviceManager,
        config: InputAudioStreamConfig,
    ) -> None:
        self._config = config
        self._manager = manager
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

    def get_audio_frames(self) -> bytes:
        if not self._stream:
            raise RuntimeError("Audio stream is not open")

        return self._stream.read(self._config.chunk_size)
