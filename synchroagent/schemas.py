from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class BaseEventSchema(BaseModel):
    event_type: str
    run_id: int | None = Field(default=None)
    timestamp: datetime = Field(default_factory=datetime.now)


class LogEventSchema(BaseEventSchema):
    event_type: Literal["process.output"] = "process.output"
    log_type: Literal["stdout", "stderr"]
    content: dict
