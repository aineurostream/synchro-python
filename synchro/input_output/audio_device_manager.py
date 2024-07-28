import logging
from dataclasses import dataclass, field
from types import TracebackType
from typing import Literal, Self

import pyaudio

from synchro.modules.audio_device import AudioDevice

logger = logging.getLogger(__name__)


@dataclass
class AudioDeviceManager:
    active_context: pyaudio.PyAudio | None = field(default=None)
    active_devices: dict[int, AudioDevice] = field(default_factory=dict)

    def __enter__(self) -> Self:
        if self.active_context is not None:
            raise RuntimeError("AudioDeviceManager is already active")

        self.active_context = pyaudio.PyAudio()

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> Literal[False]:
        if self.active_context is not None:
            self.active_context.terminate()
            self.active_context = None
        return False

    @property
    def context(self) -> pyaudio.PyAudio:
        if self.active_context is None:
            raise RuntimeError("AudioDeviceManager is not active")
        return self.active_context

    @staticmethod
    def list_default_audio_devices() -> list[AudioDevice]:
        audio = pyaudio.PyAudio()
        devices = []
        for device_info in [
            audio.get_default_input_device_info(),
            audio.get_default_output_device_info(),
        ]:
            device = AudioDevice(0, device_info)
            devices.append(device)

        audio.terminate()
        return devices

    @staticmethod
    def list_audio_devices() -> list[AudioDevice]:
        """
        Retrieve a list of audio devices available
        on the system using PyAudio library.
        """

        audio = pyaudio.PyAudio()
        devices = []

        for i in range(audio.get_device_count()):
            device_info = audio.get_device_info_by_index(i)
            device = AudioDevice(i, device_info)
            devices.append(device)

        audio.terminate()
        return devices
