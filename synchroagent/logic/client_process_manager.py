import logging
import os
import signal
import subprocess
from pathlib import Path

from synchroagent.config import default_config
from synchroagent.database.client_registry import ClientRegistry
from synchroagent.database.client_run_registry import (
    ClientRunCreate,
    ClientRunRegistry,
    ClientRunUpdate,
)
from synchroagent.database.config_registry import ConfigRegistry
from synchroagent.database.models import (
    ClientRunSchema,
    ClientSchema,
    ConfigSchema,
    RunStatus,
)
from synchroagent.utils import ensure_dir_exists

logger = logging.getLogger(__name__)


class ClientProcessManager:
    def __init__(
        self,
        client_registry: ClientRegistry,
        client_run_registry: ClientRunRegistry,
        config_registry: ConfigRegistry,
        outputs_dir: str | None = None,
    ) -> None:
        self.client_registry = client_registry
        self.client_run_registry = client_run_registry
        self.config_registry = config_registry
        self.outputs_dir = outputs_dir or default_config.outputs_dir
        self.hydra_script = default_config.hydra_script
        ensure_dir_exists(self.outputs_dir)

    def _validate_client_and_config(
        self,
        client_id: int,
        config_id: int,
    ) -> tuple[ClientSchema, ConfigSchema]:
        client = self.client_registry.get_by_id(client_id)
        if not client:
            raise ValueError(f"Client not found: {client_id}")

        config = self.config_registry.get_by_id(config_id)
        if not config:
            raise ValueError(f"Configuration not found: {config_id}")

        return client, config

    def _create_client_run(
        self,
        client_id: int,
        config_id: int,
    ) -> int:
        client_run_create = ClientRunCreate(
            client_id=client_id,
            config_id=config_id,
            status=RunStatus.CREATED,
        )

        client_run_id = self.client_run_registry.create(client_run_create)
        if not client_run_id:
            raise RuntimeError("Failed to create client run record")

        return client_run_id

    def _start_process(
        self,
        config: ConfigSchema,
        client_run_id: int,
    ) -> ClientRunSchema:
        hydra_script_path = Path(self.hydra_script).resolve()
        if not hydra_script_path.is_file():
            raise FileNotFoundError(f"Hydra script not found: {hydra_script_path}")

        python_executable = "python"
        cmd = [
            python_executable,
            str(hydra_script_path),
            "--config-name",
            config.name,
        ]

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )

            client_run_update = ClientRunUpdate(
                pid=process.pid,
                status=RunStatus.RUNNING,
            )

            self.client_run_registry.update(client_run_id, client_run_update)
            client_run = self.client_run_registry.get_by_id(client_run_id)

            if not client_run:
                raise RuntimeError(f"Failed to retrieve client run: {client_run_id}")  # noqa: TRY301

            logger.info(f"Started client run {client_run_id} with PID {process.pid}")
        except Exception as e:
            self.client_run_registry.update_status(client_run_id, RunStatus.FAILED)
            logger.exception(f"Failed to start process for run {client_run_id}")
            raise RuntimeError(f"Failed to start client process: {e}") from e
        else:
            return client_run

    def start_client(self, client_id: int, config_id: int) -> ClientRunSchema:
        try:
            _client, config = self._validate_client_and_config(client_id, config_id)
            client_run_id = self._create_client_run(client_id, config_id)
            return self._start_process(config, client_run_id)
        except Exception:
            logger.exception(f"Failed to start client {client_id}")
            raise

    def stop_client_run(self, run_id: int) -> ClientRunSchema:
        client_run = self.client_run_registry.get_by_id(run_id)
        if not client_run:
            raise ValueError(f"Client run not found: {run_id}")

        if client_run.status != RunStatus.RUNNING:
            raise ValueError(f"Client run is not running: {run_id}")

        if client_run.pid is None:
            raise ValueError(f"Client run has no process ID: {run_id}")

        try:
            os.killpg(os.getpgid(client_run.pid), signal.SIGTERM)
            logger.info(f"Sent SIGTERM to client run {run_id} (PID: {client_run.pid})")
            self.client_run_registry.update_status(run_id, RunStatus.STOPPED)
            updated_run = self.client_run_registry.get_by_id(run_id)

            if not updated_run:
                raise RuntimeError(  # noqa: TRY301
                    f"Failed to retrieve client run after stopping: {run_id}",
                )

        except ProcessLookupError as e:
            logger.warning(f"Process {client_run.pid} not found, marking as stopped")
            self.client_run_registry.update_status(run_id, RunStatus.STOPPED)

            updated_run = self.client_run_registry.get_by_id(run_id)
            if not updated_run:
                raise RuntimeError(
                    f"Failed to retrieve client run after stopping: {run_id}",
                ) from e
            return updated_run
        except Exception as e:
            logger.exception(f"Error stopping client run {run_id}")
            raise RuntimeError(f"Failed to stop client run: {e}") from e
        else:
            return updated_run

    def get_active_runs(self) -> list[ClientRunSchema]:
        return self.client_run_registry.get_active_runs()

    def get_client_runs(self, client_id: int, limit: int = 10) -> list[ClientRunSchema]:
        return self.client_run_registry.get_runs_by_client_id(client_id, limit)

    def check_process_status(self, run_id: int) -> bool:
        client_run = self.client_run_registry.get_by_id(run_id)
        if not client_run or client_run.pid is None:
            return False

        try:
            os.kill(client_run.pid, 0)
        except ProcessLookupError:
            if client_run.status == RunStatus.RUNNING:
                self.client_run_registry.update_status(run_id, RunStatus.STOPPED)
            return False
        except Exception:
            logger.exception(f"Error checking process status for run {run_id}")
            return False
        else:
            return True
