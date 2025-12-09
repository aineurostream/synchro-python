from enum import Enum
from typing import ClassVar

import numpy as np
from pydantic import BaseModel


class AudioFormatType(str, Enum):
    INT_8 = "int8"
    INT_16 = "int16"
    INT_24 = "int24"
    INT_32 = "int32"
    FLOAT_32 = "float32"


class AudioFormat(BaseModel):
    _FORMAT_TO_SAMPLE_SIZE: ClassVar[dict[AudioFormatType, int]] = {
        AudioFormatType.INT_16: 2,
    }

    _FORMAT_TO_PYAUDIO: ClassVar[dict[AudioFormatType, int]] = {
        AudioFormatType.INT_16: 2,
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


DEFAULT_AUDIO_FORMAT = AudioFormat(format_type=AudioFormatType.INT_16)
