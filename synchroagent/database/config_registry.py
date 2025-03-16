import json
import logging
from typing import Any, cast

from pydantic import BaseModel

from synchroagent.database.base_registry import BaseRegistry
from synchroagent.database.db import DatabaseConnection
from synchroagent.database.models import ConfigSchema
from synchroagent.utils import get_datetime_iso

logger = logging.getLogger(__name__)


class ConfigCreate(BaseModel):
    name: str
    content: dict[str, Any]
    description: str | None = None


class ConfigUpdate(BaseModel):
    name: str | None = None
    content: dict[str, Any] | None = None
    description: str | None = None


class ConfigRegistry(BaseRegistry[ConfigSchema, ConfigCreate, ConfigUpdate]):
    def __init__(self, db_connection: DatabaseConnection) -> None:
        super().__init__(db_connection, "configs", ConfigSchema)

    def _row_to_model(self, row: dict[str, Any]) -> ConfigSchema:
        if "content" in row and isinstance(row["content"], str):
            try:
                row["content"] = json.loads(row["content"])
            except json.JSONDecodeError:
                logger.exception(
                    f"Failed to parse JSON content for config ID {row.get('id')}",
                )
                row["content"] = {}
        return cast(ConfigSchema, ConfigSchema.model_validate(row))

    def model_to_dict(self, model: ConfigSchema) -> dict[str, Any]:
        return cast(dict[str, Any], model.model_dump())

    def model_create_to_dict(self, model: ConfigCreate) -> dict[str, Any]:
        data = model.model_dump(exclude_unset=True)
        if "content" in data and isinstance(data["content"], dict):
            data["content"] = json.dumps(data["content"])
        data["created_at"] = get_datetime_iso()
        data["updated_at"] = get_datetime_iso()

        return cast(dict[str, Any], data)

    def model_update_to_dict(self, model: ConfigUpdate) -> dict[str, Any]:
        data = model.model_dump(exclude_unset=True, exclude_none=True)
        if "content" in data and isinstance(data["content"], dict):
            data["content"] = json.dumps(data["content"])

        # Update timestamp
        data["updated_at"] = get_datetime_iso()

        return cast(dict[str, Any], data)
