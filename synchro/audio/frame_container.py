from dataclasses import dataclass
from typing import Self

from synchro.config.audio_format import AudioFormat
from synchro.config.commons import StreamConfig


@dataclass
class FrameContainer:
    @classmethod
    def from_config(cls, config: StreamConfig, data: bytes = b"") -> Self:
        if config.audio_format is None:
            raise ValueError("Audio format is required")
        if config.rate is None:
            raise ValueError("Rate is required")

        return cls(
            language=config.language,
            audio_format=config.audio_format,
            rate=config.rate,
            frame_data=data,
        )

    language: str
    audio_format: AudioFormat
    rate: int
    frame_data: bytes

    def __len__(self) -> int:
        return len(self.frame_data) // self.audio_format.sample_size

    def __str__(self) -> str:
        return f"FC({self.language}, {self.audio_format}, {self.rate} [{len(self)}])"

    def __repr__(self) -> str:
        return str(self)

    def append(self, other: Self) -> None:
        self.frame_data += other.frame_data

    def append_bytes(self, frame_data: bytes) -> None:
        self.frame_data += frame_data

    def clear(self) -> None:
        self.frame_data = b""

    def shrink(self, frames_count: int) -> None:
        if frames_count <= 0:
            raise ValueError("Count must be positive")

        n = int(frames_count * self.audio_format.sample_size)

        self.frame_data = self.frame_data[n:]

    def length_ms(self) -> int:
        return (
            len(self.frame_data) * 1000 // (self.rate * self.audio_format.sample_size)
        )
