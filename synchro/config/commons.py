from collections.abc import Callable

from pydantic import BaseModel

from synchro.config.audio_format import AudioFormat

MIN_STEP_LENGTH_SECS = 0.5
MIN_WORKING_STEP_LENGTH_SECS = MIN_STEP_LENGTH_SECS * 2

PREFERRED_BUFFER_SIZE_SEC = 0.2
MIN_BUFFER_SIZE_SEC = 0.03

NodeEventsCallback = Callable[[str, dict], None]


class StreamConfig(BaseModel):
    language: str
    audio_format: AudioFormat
    rate: int
