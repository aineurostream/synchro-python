from pydantic import BaseModel

from synchro.config.audio_format import AudioFormat

MIN_STEP_LENGTH_SECS = 0.1
MIN_WORKING_STEP_LENGTH_SECS = 0.5


class StreamConfig(BaseModel):
    language: str
    audio_format: AudioFormat
    rate: int
