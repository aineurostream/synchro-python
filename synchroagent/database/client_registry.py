import logging
from typing import Any, cast

from pydantic import BaseModel

from synchroagent.database.base_registry import BaseRegistry
from synchroagent.database.db import DatabaseConnection
from synchroagent.database.models import ClientSchema

logger = logging.getLogger(__name__)


class ClientCreate(BaseModel):
    name: str
    config_id: int
    description: str | None = None


class ClientUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class ClientRegistry(BaseRegistry[ClientSchema, ClientCreate, ClientUpdate]):
    def __init__(self, db_connection: DatabaseConnection) -> None:
        super().__init__(db_connection, "clients", ClientSchema)

    def _row_to_model(self, row: dict[str, Any]) -> ClientSchema:
        return cast(ClientSchema, ClientSchema.model_validate(row))

    def model_to_dict(self, model: ClientSchema) -> dict[str, Any]:
        return cast(dict[str, Any], model.model_dump(mode="json"))

    def model_create_to_dict(self, model: ClientCreate) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            model.model_dump(mode="json", exclude_unset=True),
        )

    def model_update_to_dict(self, model: ClientUpdate) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            model.model_dump(mode="json", exclude_unset=True, exclude_none=True),
        )

    def get_clients_by_config_id(self, config_id: int) -> list[ClientSchema]:
        return self.filter(config_id=config_id)
