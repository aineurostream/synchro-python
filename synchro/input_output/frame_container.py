from dataclasses import dataclass
from typing import Self

from synchro.input_output.audio_stream_capture import SAMPLE_SIZE_BYTES_INT_16
from synchro.input_output.schemas import InputStreamEntity


@dataclass
class FrameContainer:
    sample_size: int
    rate: int
    frame_data: bytes

    def __len__(self) -> int:
        return len(self.frame_data) // self.sample_size

    def append(self, other: Self) -> None:
        self.frame_data += other.frame_data

    def append_bytes(self, frame_data: bytes) -> None:
        self.frame_data += frame_data

    def clear(self) -> None:
        self.frame_data = b""

    def shrink(self, frames_count: int) -> None:
        if frames_count <= 0:
            raise ValueError("Count must be positive")

        n = int(frames_count * self.sample_size)

        self.frame_data = self.frame_data[n:]

    def length_ms(self) -> int:
        return len(self.frame_data) * 1000 // (self.rate * self.sample_size)


@dataclass
class InputFrameContainer(FrameContainer):
    source: InputStreamEntity

    @classmethod
    def create_empty(cls, source: InputStreamEntity) -> Self:
        return cls(
            source=source,
            sample_size=SAMPLE_SIZE_BYTES_INT_16,
            rate=source.config.rate,
            frame_data=b"",
        )
