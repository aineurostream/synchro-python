import logging
from pathlib import Path

from synchroagent.database.client_run_registry import ClientRunRegistry, ClientRunUpdate
from synchroagent.database.log_registry import LogCreate, LogRegistry
from synchroagent.database.models import LogSchema, LogType

logger = logging.getLogger(__name__)


class LogManager:
    def __init__(
        self,
        log_registry: LogRegistry,
        client_run_registry: ClientRunRegistry,
    ) -> None:
        self.log_registry = log_registry
        self.client_run_registry = client_run_registry

    def collect_logs(self, client_run_id: int) -> int:
        client_run = self.client_run_registry.get_by_id(client_run_id)
        if not client_run:
            msg = f"Client run not found: {client_run_id}"
            raise ValueError(msg)

        if not client_run.output_dir:
            msg = f"Client run has no output directory: {client_run_id}"
            raise ValueError(msg)
        output_dir = Path(client_run.output_dir)
        if not output_dir.exists():
            msg = f"Output directory not found: {output_dir}"
            raise ValueError(msg)

        log_file = Path(output_dir) / "hydra_run.log"
        if not log_file.exists():
            msg = f"No log file found in {output_dir}"
            raise ValueError(msg)
        log_contents = self._read_log_file(log_file)
        log_create = LogCreate(
            client_run_id=client_run_id,
            content=log_contents,
            log_type=LogType.APPLICATION,
        )

        log = self.log_registry.create(log_create)
        if not log:
            msg = "Failed to create log record in database"
            raise ValueError(msg)
        client_run_update = ClientRunUpdate(log_id=log.id)
        self.client_run_registry.update(client_run_id, client_run_update)

        return log.id

    def _read_log_file(self, log_file: Path) -> str:
        try:
            with log_file.open(encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            msg = f"Failed to read log file: {log_file}"
            raise ValueError(msg) from e

    def get_log(self, log_id: int) -> LogSchema | None:
        return self.log_registry.get_by_id(log_id)

    def get_logs_by_client_run(self, client_run_id: int) -> list[LogSchema]:
        return self.log_registry.get_logs_by_client_run(client_run_id)
