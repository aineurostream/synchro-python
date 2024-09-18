from enum import Enum
from typing import ClassVar, Self

import numpy as np
import pyaudio
from pydantic import BaseModel


class AudioFormatType(str, Enum):
    INT_16 = "int16"


class AudioFormat(BaseModel):
    @classmethod
    def from_pyaudio_format(cls, pyaudio_format_request: int) -> Self:
        for audio_format_type, pyaudio_format in cls._FORMAT_TO_PYAUDIO.items():
            if pyaudio_format == pyaudio_format_request:
                return cls(format_type=audio_format_type)
        raise ValueError(f"Unknown pyaudio format: {pyaudio_format_request}")

    _FORMAT_TO_SAMPLE_SIZE: ClassVar[dict[AudioFormatType, int]] = {
        AudioFormatType.INT_16: 2,
    }

    _FORMAT_TO_PYAUDIO: ClassVar[dict[AudioFormatType, int]] = {
        AudioFormatType.INT_16: pyaudio.paInt16,
    }

    _FORMAT_TO_NUMPY: ClassVar[dict[AudioFormatType, type]] = {
        AudioFormatType.INT_16: np.int16,
    }

    format_type: AudioFormatType

    @property
    def sample_size(self) -> int:
        return self._FORMAT_TO_SAMPLE_SIZE[self.format_type]

    @property
    def pyaudio_format(self) -> int:
        return self._FORMAT_TO_PYAUDIO[self.format_type]

    @property
    def numpy_format(self) -> type:
        return self._FORMAT_TO_NUMPY[self.format_type]

    def __str__(self) -> str:
        return f"AF({self.format_type.value})"

    def __repr__(self) -> str:
        return str(self)
