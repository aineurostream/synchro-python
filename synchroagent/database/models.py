from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"


class LogType(str, Enum):
    STDOUT = "stdout"
    STDERR = "stderr"
    APPLICATION = "application"


IdField = Annotated[int, Field(ge=0, default=0)]


class BaseSchema(BaseModel):
    model_config = {
        "validate_assignment": True,
        "extra": "forbid",
    }

    id: IdField


# Base models
class ClientSchema(BaseSchema):
    name: str
    description: str | None = None
    config_id: int | None = None


class ConfigSchema(BaseSchema):
    name: str
    content: dict[str, Any]
    description: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class ReportSchema(BaseSchema):
    client_id: int
    content: str | None = None
    size: int | None = None
    generated_at: str | None = None


class ClientRunSchema(BaseSchema):
    client_id: int
    config_id: int
    pid: int | None = None
    status: RunStatus = RunStatus.CREATED
    output_dir: str | None = None
    report_id: int | None = None
    log_id: int | None = None
    exit_code: int | None = None
    started_at: str | None = None
    finished_at: str | None = None


class LogSchema(BaseSchema):
    client_run_id: int
    content: str
    log_type: LogType
    created_at: str | None = None
