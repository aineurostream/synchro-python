from dataclasses import dataclass

import pyaudio


@dataclass
class BaseAudioStreamConfig:
    device: int
    audio_format: int = pyaudio.paInt16
    channels: int = 1
    rate: int = 44100


@dataclass
class InputAudioStreamConfig(BaseAudioStreamConfig):
    chunk_size: int = 1024


@dataclass
class OutputAudioStreamConfig(BaseAudioStreamConfig):
    pass
