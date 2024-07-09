from dataclasses import dataclass
from typing import Self

ChannelLocaleRaw = tuple[int, str]


@dataclass
class ChannelLocale:
    @classmethod
    def from_raw(cls, raw: ChannelLocaleRaw) -> Self:
        return cls(channel=raw[0], locale=raw[1])

    channel: int
    locale: str
