from dataclasses import dataclass
from typing import Self

from synchro.config.audio_format import AudioFormat


@dataclass
class FrameContainer:
    audio_format: AudioFormat
    rate: int
    frame_data: bytes

    def __len__(self) -> int:
        return len(self.frame_data) // self.audio_format.sample_size

    def __repr__(self) -> str:
        return str(self)

    def __str__(self) -> str:
        return f"FC({self.audio_format}, {self.rate} [{len(self.frame_data)}b])"

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

    def frames_to_bytes(self, frames: int) -> bytes:
        return self.frame_data[: frames * self.audio_format.sample_size]

    def length_ms(self) -> int:
        return (
            len(self.frame_data) * 1000 // (self.rate * self.audio_format.sample_size)
        )

    def length_frames(self) -> int:
        return len(self)
