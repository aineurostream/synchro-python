from dataclasses import dataclass, field
from multiprocessing import Queue

import pyaudio


@dataclass
class BaseAudioStreamConfig:
    device: int
    language: str
    audio_format: int = pyaudio.paInt16
    channels: int = 1
    rate: int = 44100


@dataclass
class InputAudioStreamConfig(BaseAudioStreamConfig):
    chunk_size: int = 1024


@dataclass
class OutputAudioStreamConfig(BaseAudioStreamConfig):
    pass


@dataclass
class InputStreamEntity:
    id: int
    config: InputAudioStreamConfig
    queue: Queue = field(default_factory=Queue)


@dataclass
class OutputStreamEntity:
    id: int
    config: OutputAudioStreamConfig
    queue: Queue = field(default_factory=Queue)
