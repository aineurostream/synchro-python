# synchro/config/audio_format.py

from __future__ import annotations
from enum import Enum
from typing import ClassVar, Union

import numpy as np
from pydantic import BaseModel


class AudioFormatType(str, Enum):
    INT_8 = "int8"
    INT_16 = "int16"
    INT_24 = "int24"
    INT_32 = "int32"
    FLOAT_32 = "float32"


class AudioFormat(BaseModel):
    """
    Унифицированное описание формата с:
    - sample_size: размер сэмпла в байтах (int24 = 3 байта!),
    - numpy_format: dtype для массивов/CPU (int24 представляем через int32),
    - sounddevice_dtype: dtype для sounddevice (поддерживает 'int24' строкой),
    - pyaudio_format: константа для PyAudio, если установлен (иначе ValueError).
    """

    _SAMPLE_WIDTH_TO_FORMAT: ClassVar[dict[int, AudioFormatType]] = {
        1: AudioFormatType.INT_8,
        2: AudioFormatType.INT_16,
        3: AudioFormatType.INT_24,
        4: AudioFormatType.INT_32,   # по умолчанию считаем это int32 PCM
    }

    # Размеры сэмпла (байт)
    _FORMAT_TO_SAMPLE_SIZE: ClassVar[dict[AudioFormatType, int]] = {
        AudioFormatType.INT_8: 1,
        AudioFormatType.INT_16: 2,
        AudioFormatType.INT_24: 3,
        AudioFormatType.INT_32: 4,
        AudioFormatType.FLOAT_32: 4,
    }

    # dtype для numpy-операций в памяти (int24 храним через int32)
    _FORMAT_TO_NUMPY: ClassVar[dict[AudioFormatType, Union[type, np.dtype]]] = {
        AudioFormatType.INT_8: np.int8,
        AudioFormatType.INT_16: np.int16,
        AudioFormatType.INT_24: np.int32,   # нет int24 в numpy; используем int32 как контейнер
        AudioFormatType.INT_32: np.int32,
        AudioFormatType.FLOAT_32: np.float32,
    }

    # dtype для sounddevice (он умеет 'int24' строкой)
    _FORMAT_TO_SD: ClassVar[dict[AudioFormatType, Union[str, np.dtype]]] = {
        AudioFormatType.INT_8: np.int8,
        AudioFormatType.INT_16: np.int16,
        AudioFormatType.INT_24: "int24",
        AudioFormatType.INT_32: np.int32,
        AudioFormatType.FLOAT_32: np.float32,
    }

    # Константы PyAudio — подгружаем лениво, чтобы не тянуть зависимость
    _FORMAT_TO_PYAUDIO: ClassVar[dict[AudioFormatType, int] | None] = None

    format_type: AudioFormatType

    @classmethod
    def from_sample_width(cls, sampwidth: int, *, is_float: bool = False) -> "AudioFormat":
        if is_float and sampwidth == 4:
            return cls(format_type=AudioFormatType.FLOAT_32)
        
        return cls(format_type=cls._SAMPLE_WIDTH_TO_FORMAT[sampwidth])

    @property
    def sample_size(self) -> int:
        try:
            return self._FORMAT_TO_SAMPLE_SIZE[self.format_type]
        except KeyError:
            raise ValueError(f"Unsupported sample size mapping for {self.format_type}")

    @property
    def numpy_format(self) -> Union[type, np.dtype]:
        """
        dtype для numpy-буферов/обработки. Для INT_24 возвращается int32 —
        это осознанно: вы сами решаете, как упаковывать/распаковывать 24-битные 3-байтовые семплы.
        """
        try:
            return self._FORMAT_TO_NUMPY[self.format_type]
        except KeyError:
            raise ValueError(f"Unsupported numpy dtype mapping for {self.format_type}")

    @property
    def sounddevice_dtype(self) -> Union[str, np.dtype]:
        """
        dtype, который можно напрямую отдавать в sounddevice.Stream(..., dtype=...).
        Для 24 бит — строка 'int24'.
        """
        try:
            return self._FORMAT_TO_SD[self.format_type]
        except KeyError:
            raise ValueError(f"Unsupported sounddevice dtype mapping for {self.format_type}")

    @property
    def pyaudio_format(self) -> int:
        """
        Константа для PyAudio (paInt16, paInt24 и т. п.). Вычисляется лениво.
        Если PyAudio не установлен или тип не поддержан — поднимаем ValueError.
        """
        if self._FORMAT_TO_PYAUDIO is None:
            try:
                import pyaudio  # type: ignore
            except Exception as e:
                raise ValueError(
                    "PyAudio is not installed; pyaudio_format is unavailable"
                ) from e
            # Собираем маппинг только если библиотека есть
            self.__class__._FORMAT_TO_PYAUDIO = {
                AudioFormatType.INT_8: getattr(pyaudio, "paInt8"),
                AudioFormatType.INT_16: getattr(pyaudio, "paInt16"),
                AudioFormatType.INT_24: getattr(pyaudio, "paInt24"),
                AudioFormatType.INT_32: getattr(pyaudio, "paInt32"),
                AudioFormatType.FLOAT_32: getattr(pyaudio, "paFloat32"),
            }
        try:
            return self._FORMAT_TO_PYAUDIO[self.format_type]  # type: ignore[index]
        except KeyError:
            raise ValueError(f"Unsupported PyAudio format for {self.format_type}")

    def __str__(self) -> str:
        return f"AF({self.format_type.value})"

    def __repr__(self) -> str:
        return str(self)


# Формат «по умолчанию»
DEFAULT_AUDIO_FORMAT = AudioFormat(format_type=AudioFormatType.INT_16)
