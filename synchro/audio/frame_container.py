import numpy as np

from synchro.config.commons import StreamConfig


class FrameContainer(StreamConfig):
    model_config = {
        "arbitrary_types_allowed": True,
    }

    @classmethod
    def from_config(
        cls,
        config: StreamConfig,
        frame_data: bytes = b"",
        channels: int | None = None,
    ) -> "FrameContainer":
        return cls(
            audio_format=config.audio_format,
            rate=config.rate,
            frame_data=frame_data,
            channels=config.channels,
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
            "<FrameContainer"
            f" {self.audio_format=}"
            f" {self.rate=} "
            f" {self.channels=} "
            f" length={len(self.frame_data)}b/{self.length_ms}ms"
            ">"
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
        return not bool(self)

    def clone(self) -> "FrameContainer":
        return FrameContainer(
            audio_format=self.audio_format,
            rate=self.rate,
            frame_data=self.frame_data,
            channels=self.channels,
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

    def as_np(self) -> np.ndarray:
        return np.frombuffer(
            buffer=self.frame_data, 
            dtype=self.audio_format.numpy_format,
        )

    def to_pcm16_bytes(self) -> bytes:
        import numpy as np
        raw = self.frame_data or b""
        ft = self.audio_format.format_type

        if not raw:
            return b""

        if ft.name == "INT_16":
            return raw

        if ft.name == "FLOAT_32":
            # ⬇️ подрежем до кратности 4
            n4 = (len(raw) // 4) * 4
            if n4 != len(raw):
                # можно залогировать warning
                raw = raw[:n4]
            x = np.frombuffer(raw, dtype="<f4").astype(np.float32)
            x = np.clip(x, -1.0, 1.0)
            return (x * 32767.0).astype("<i2").tobytes()

        if ft.name == "INT_8":
            x = np.frombuffer(raw, dtype="<i1").astype(np.int16)
            return (x * 256).astype("<i2").tobytes()

        if ft.name == "INT_24":
            b = np.frombuffer(raw, dtype=np.uint8)
            n3 = (len(b) // 3) * 3
            if n3 != len(b):
                b = b[:n3]
            b = b.reshape(-1, 3)
            v = (b[:,0].astype(np.int32)
                | (b[:,1].astype(np.int32) << 8)
                | (b[:,2].astype(np.int32) << 16))
            v = (v << 8) >> 8
            return (v >> 8).astype("<i2").tobytes()

        if ft.name == "INT_32":
            n4 = (len(raw) // 4) * 4
            if n4 != len(raw):
                raw = raw[:n4]
            v = np.frombuffer(raw, dtype="<i4").astype(np.int32)
            return (v >> 16).astype("<i2").tobytes()

        raise ValueError(f"Unsupported format: {ft}")
