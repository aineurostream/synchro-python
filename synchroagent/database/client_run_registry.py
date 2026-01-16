import logging
from typing import Any, cast

from pydantic import BaseModel

from synchroagent.database.base_registry import BaseRegistry
from synchroagent.database.db import DatabaseConnection
from synchroagent.database.models import ClientRunSchema, RunStatus
from synchroagent.utils import get_datetime_iso

logger = logging.getLogger(__name__)


class ClientRunCreate(BaseModel):
    client_id: int
    config_id: int
    status: RunStatus = RunStatus.CREATED
    output_dir: str | None = None
    started_at: str | None = None


class ClientRunUpdate(BaseModel):
    client_id: int | None = None
    config_id: int | None = None
    pid: int | None = None
    status: RunStatus | None = None
    output_dir: str | None = None
    report_id: int | None = None
    log_id: int | None = None
    exit_code: int | None = None


class ClientRunRegistry(
    BaseRegistry[ClientRunSchema, ClientRunCreate, ClientRunUpdate],
):
    def __init__(self, db_connection: DatabaseConnection) -> None:
        super().__init__(db_connection, "client_runs", ClientRunSchema)

    def _row_to_model(self, row: dict[str, Any]) -> ClientRunSchema:
        return cast(ClientRunSchema, ClientRunSchema.model_validate(row))

    def model_to_dict(self, model: ClientRunSchema) -> dict[str, Any]:
        return cast(dict[str, Any], model.model_dump(mode="json"))

    def model_create_to_dict(self, model: ClientRunCreate) -> dict[str, Any]:
        data = model.model_dump(mode="json", exclude_unset=True)
        data["started_at"] = data.get("started_at") or get_datetime_iso()

        return cast(dict[str, Any], data)

    def model_update_to_dict(self, model: ClientRunUpdate) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            model.model_dump(mode="json", exclude_unset=True, exclude_none=True),
        )

    def update_run_status(
        self,
        run: ClientRunSchema,
        status: RunStatus,
    ) -> ClientRunSchema | None:
        return self.update_status(run.id, status)

    def update_status(self, run_id: int, status: RunStatus) -> ClientRunSchema | None:
        data = {"status": status.value}
        if status in (RunStatus.FAILED, RunStatus.STOPPED):
            data["finished_at"] = get_datetime_iso()

        set_clause = ", ".join([f"{k} = ?" for k in data])
        values = (*data.values(), run_id)

        query = f"""
            UPDATE {self.table_name}
            SET {set_clause}
            WHERE id = ?
        """

        self.db.execute(query, values)
        return self.get_by_id(run_id)

    def get_active_runs(self) -> list[ClientRunSchema]:
        query = f"""
            SELECT * FROM {self.table_name}
            WHERE status = ?
            ORDER BY started_at DESC
        """
        results = self.db.execute(query, (RunStatus.RUNNING.value,))
        return [self._row_to_model(row) for row in results]

    def get_runs_by_client_id(
        self,
        client_id: int,
        limit: int = 10,
    ) -> list[ClientRunSchema]:
        query = f"""
            SELECT * FROM {self.table_name}
            WHERE client_id = ?
            ORDER BY started_at DESC
            LIMIT {limit}
        """
        results = self.db.execute(query, (client_id,))
        return [self._row_to_model(row) for row in results]
