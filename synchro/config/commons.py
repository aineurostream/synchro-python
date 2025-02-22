from collections.abc import Callable

from pydantic import BaseModel

from synchro.config.audio_format import AudioFormat

MIN_STEP_LENGTH_SECS = 0.5
MIN_WORKING_STEP_LENGTH_SECS = MIN_STEP_LENGTH_SECS * 2
MIN_STEP_NON_GENERATING_SECS = MIN_STEP_LENGTH_SECS / 30.0

MEDIUM_BUFFER_SIZE_SEC = 0.5
LONG_BUFFER_SIZE_SEC = 2.0

NodeEventsCallback = Callable[[str, dict], None]


class StreamConfig(BaseModel):
    audio_format: AudioFormat
    rate: int
