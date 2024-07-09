from types import TracebackType
from typing import Literal

import pyaudio

from synchro.input_output.audio_device_manager import AudioDeviceManager
from synchro.input_output.configs import OutputAudioStreamConfig


class AudioStreamOutput:
    def __init__(
        self,
        manager: AudioDeviceManager,
        config: OutputAudioStreamConfig,
    ) -> None:
        self._config = config
        self._manager = manager
        self._stream: pyaudio.Stream | None = None

    def __enter__(self) -> None:
        self._stream = self._manager.context.open(
            format=self._config.audio_format,
            channels=self._config.channels,
            rate=self._config.rate,
            output=True,
            output_device_index=self._config.device,
        )

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

    def write_audio_frames(self, frames: bytes) -> None:
        if self._stream is None:
            raise RuntimeError("Audio stream is not open")

        self._stream.write(frames)
