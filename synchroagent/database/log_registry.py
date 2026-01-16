import logging
from typing import Any, cast

from pydantic import BaseModel

from synchroagent.database.base_registry import BaseRegistry
from synchroagent.database.db import DatabaseConnection
from synchroagent.database.models import LogSchema, LogType
from synchroagent.utils import get_datetime_iso

logger = logging.getLogger(__name__)


class LogCreate(BaseModel):
    client_run_id: int
    content: str
    log_type: LogType
    created_at: str | None = None


class LogUpdate(BaseModel):
    client_run_id: int | None = None
    content: str | None = None
    log_type: LogType | None = None


class LogRegistry(BaseRegistry[LogSchema, LogCreate, LogUpdate]):
    def __init__(self, db_connection: DatabaseConnection) -> None:
        super().__init__(db_connection, "logs", LogSchema)

    def _row_to_model(self, row: dict[str, Any]) -> LogSchema:
        return cast(LogSchema, LogSchema.model_validate(row))

    def model_to_dict(self, model: LogSchema) -> dict[str, Any]:
        return cast(dict[str, Any], model.model_dump(mode="json"))

    def model_create_to_dict(self, model: LogCreate) -> dict[str, Any]:
        data = model.model_dump(mode="json", exclude_unset=True)
        data["created_at"] = data.get("created_at") or get_datetime_iso()

        return cast(dict[str, Any], data)

    def model_update_to_dict(self, model: LogUpdate) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            model.model_dump(mode="json", exclude_unset=True, exclude_none=True),
        )

    def get_logs_by_client_run(self, client_run_id: int) -> list[LogSchema]:
        return self.filter(client_run_id=client_run_id)
