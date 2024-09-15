from dataclasses import dataclass
from typing import Self

from synchro.audio.frame_container import FrameContainer
from synchro.config.commons import StreamConfig


@dataclass
class GraphFrameContainer(FrameContainer):
    @classmethod
    def from_config(
        cls,
        source: str,
        config: StreamConfig,
        data: bytes = b"",
    ) -> Self:
        if config.audio_format is None:
            raise ValueError("Audio format is required")
        if config.rate is None:
            raise ValueError("Rate is required")

        return cls(
            source=source,
            language=config.language,
            audio_format=config.audio_format,
            rate=config.rate,
            frame_data=data,
        )

    @classmethod
    def from_frame_container(
        cls,
        source: str,
        language: str,
        frame_container: FrameContainer,
    ) -> Self:
        return cls(
            source=source,
            language=language,
            audio_format=frame_container.audio_format,
            rate=frame_container.rate,
            frame_data=frame_container.frame_data,
        )

    source: str
    language: str

    def __str__(self) -> str:
        return f"GFC({self.source}, {self.language}, {super().__str__()})"

    def __repr__(self) -> str:
        return str(self)
