import logging
from typing import Any, cast

from pydantic import BaseModel

from synchroagent.database.base_registry import BaseRegistry
from synchroagent.database.db import DatabaseConnection
from synchroagent.database.models import ReportSchema
from synchroagent.utils import get_datetime_iso

logger = logging.getLogger(__name__)


class ReportCreate(BaseModel):
    client_id: int
    content: str
    generated_at: str | None = None


class ReportUpdate(BaseModel):
    pass


class ReportRegistry(BaseRegistry[ReportSchema, ReportCreate, ReportUpdate]):
    def __init__(self, db_connection: DatabaseConnection) -> None:
        super().__init__(db_connection, "reports", ReportSchema)

    def _row_to_model(self, row: dict[str, Any]) -> ReportSchema:
        return cast(ReportSchema, ReportSchema.model_validate(row))

    def model_to_dict(self, model: ReportSchema) -> dict[str, Any]:
        return cast(dict[str, Any], model.model_dump(mode="json"))

    def model_create_to_dict(self, model: ReportCreate) -> dict[str, Any]:
        data = model.model_dump(exclude_unset=True)
        if "content" in data and data["content"] and "size" not in data:
            data["size"] = len(data["content"].encode("utf-8"))
        data["generated_at"] = data.get("generated_at") or get_datetime_iso()

        return cast(dict[str, Any], data)

    def model_update_to_dict(self, model: ReportUpdate) -> dict[str, Any]:
        raise NotImplementedError("Report updates are not supported")

    def get_reports_by_client_id(self, client_id: int) -> list[ReportSchema]:
        return self.filter(client_id=client_id)
