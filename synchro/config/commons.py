from pydantic import BaseModel

from synchro.config.audio_format import AudioFormat


class StreamConfig(BaseModel):
    language: str
    audio_format: AudioFormat
    rate: int
