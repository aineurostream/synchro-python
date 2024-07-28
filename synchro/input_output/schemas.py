from dataclasses import dataclass, field
from queue import Queue

import pyaudio


@dataclass(frozen=True)
class BaseAudioStreamConfig:
    device: int
    language: str
    audio_format: int = pyaudio.paInt16
    channels: int = 1
    rate: int = 44100


@dataclass(frozen=True)
class InputAudioStreamConfig(BaseAudioStreamConfig):
    chunk_size: int = 1024


@dataclass(frozen=True)
class OutputAudioStreamConfig(BaseAudioStreamConfig):
    pass


@dataclass(frozen=True)
class InputStreamEntity:
    id: str
    config: InputAudioStreamConfig
    queue: Queue = field(default_factory=Queue)


@dataclass(frozen=True)
class OutputStreamEntity:
    id: str
    config: OutputAudioStreamConfig
    queue: Queue = field(default_factory=Queue)
