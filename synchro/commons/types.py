from dataclasses import dataclass
from typing import Self

ChannelLocaleRaw = tuple[int, int, str]


@dataclass
class ChannelLocale:
    @classmethod
    def from_raw(cls, raw: ChannelLocaleRaw) -> Self:
        return cls(device=raw[0], channel=raw[1], language=raw[2])

    device: int
    channel: int
    language: str
