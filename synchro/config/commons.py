from collections.abc import Callable

from pydantic import BaseModel

from synchro.config.audio_format import AudioFormat

MEDIUM_BUFFER_SIZE_SEC = 0.5
LONG_BUFFER_SIZE_SEC = 2.0

NodeEventsCallback = Callable[[str, dict], None]


class StreamConfig(BaseModel):
    audio_format: AudioFormat
    rate: int
    channels: int