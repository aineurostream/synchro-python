from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import UUID4, BaseModel, Field


class ClientStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    STOPPED = "stopped"
    UNKNOWN = "unknown"


class AiConfig(BaseModel):
    uuid: UUID4
    name: str | None = None
    config: dict = Field(default_factory=dict)


class PipelineConfig(BaseModel):
    uuid: UUID4
    name: str | None = None
    config: dict = Field(default_factory=dict)


class ClientConfig(BaseModel):
    uuid: UUID4
    name: str | None = None
    ai: AiConfig = Field(default_factory=AiConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)


class Client(BaseModel):
    uuid: UUID4
    name: str
    config_path: str
    status: ClientStatus
    pid: int | None = None
    start_time: datetime
    end_time: datetime | None = None
    output_dir: str | None = None
    report_path: str | None = None


class BaseEventSchema(BaseModel):
    event_type: str
    run_id: int | None = Field(default=None)
    timestamp: datetime = Field(default_factory=datetime.now)


class LogEventSchema(BaseEventSchema):
    event_type: Literal["process.output"] = "process.output"
    log_type: Literal["stdout", "stderr"]
    content: str
