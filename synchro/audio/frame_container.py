from synchro.config.commons import StreamConfig


class FrameContainer(StreamConfig):
    @classmethod
    def from_config(
        cls,
        config: StreamConfig,
        frame_data: bytes = b"",
    ) -> "FrameContainer":
        return cls(
            audio_format=config.audio_format,
            rate=config.rate,
            frame_data=frame_data,
        )

    frame_data: bytes

    def __len__(self) -> int:
        return len(self.frame_data) // self.audio_format.sample_size

    def __bool__(self) -> bool:
        return len(self.frame_data) > 0

    def __repr__(self) -> str:
        return str(self)

    def __str__(self) -> str:
        return (
            "FC("
            f"{self.audio_format}, {self.rate} "
            f"[{len(self.frame_data)}b/{self.length_ms}ms]"
            ")"
        )

    @property
    def length_ms(self) -> int:
        return (
            len(self.frame_data) * 1000 // (self.rate * self.audio_format.sample_size)
        )

    @property
    def length_secs(self) -> float:
        return self.length_ms / 1000

    @property
    def length_frames(self) -> int:
        return len(self)

    @property
    def is_empty(self) -> bool:
        return bool(self)

    def clone(self) -> "FrameContainer":
        return FrameContainer(
            audio_format=self.audio_format,
            rate=self.rate,
            frame_data=self.frame_data,
        )

    def get_config(self) -> StreamConfig:
        return StreamConfig(
            audio_format=self.audio_format,
            rate=self.rate,
        )

    def append(self, other: "FrameContainer") -> "FrameContainer":
        if self.audio_format != other.audio_format:
            raise ValueError("Audio formats are different")
        if self.rate != other.rate:
            raise ValueError("Rates are different")
        return FrameContainer.from_config(self, self.frame_data + other.frame_data)

    def append_inp(self, other: "FrameContainer") -> None:
        if self.audio_format != other.audio_format:
            raise ValueError("Audio formats are different")
        if self.rate != other.rate:
            raise ValueError("Rates are different")
        self.append_bytes_inp(other.frame_data)

    def append_bytes(self, frame_data: bytes) -> "FrameContainer":
        return FrameContainer.from_config(self, self.frame_data + frame_data)

    def append_bytes_inp(self, frame_data: bytes) -> None:
        self.frame_data += frame_data

    def to_empty(self) -> "FrameContainer":
        return FrameContainer.from_config(self)

    def with_new_data(self, frame_data: bytes) -> "FrameContainer":
        return self.to_empty().append_bytes(frame_data)

    def get_begin_frames(self, frames_count: int) -> "FrameContainer":
        n = frames_count * self.audio_format.sample_size
        return FrameContainer.from_config(self, self.frame_data[:n])

    def get_end_frames(self, frames_count: int) -> "FrameContainer":
        n = frames_count * self.audio_format.sample_size
        return FrameContainer.from_config(self, self.frame_data[-n:])

    def get_end_seconds(self, seconds: float) -> "FrameContainer":
        seconds_in_bytes = self._seconds_to_bytes(seconds)
        return FrameContainer.from_config(self, self.frame_data[-seconds_in_bytes:])

    def _seconds_to_bytes(self, seconds: float) -> int:
        return int(seconds * float(self.rate)) * self.audio_format.sample_size
