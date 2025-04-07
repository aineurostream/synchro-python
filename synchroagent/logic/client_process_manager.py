import logging
import os
import signal
import subprocess
import uuid
from pathlib import Path

import yaml

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
from synchroagent.logic.client_process_monitor import ClientProcessMonitor
from synchroagent.logic.log_manager import LogManager
from synchroagent.logic.report_manager import ReportManager
from synchroagent.utils import ensure_dir_exists

logger = logging.getLogger(__name__)


class ClientProcessManager:
    def __init__(
        self,
        client_registry: ClientRegistry,
        client_run_registry: ClientRunRegistry,
        config_registry: ConfigRegistry,
        log_manager: LogManager,
        report_manager: ReportManager,
        outputs_dir: str | None = None,
    ) -> None:
        self.client_registry = client_registry
        self.client_run_registry = client_run_registry
        self.config_registry = config_registry
        self.log_manager = log_manager
        self.report_manager = report_manager
        self.outputs_dir = outputs_dir or default_config.outputs_dir
        self.hydra_script = default_config.hydra_script

        self.process_monitor = ClientProcessMonitor(client_run_registry)
        self.process_monitor.set_process_completed_callback(self._on_process_completed)
        self.process_monitor.start()

        ensure_dir_exists(Path(self.outputs_dir))

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

        client_run = self.client_run_registry.create(client_run_create)
        if not client_run:
            raise RuntimeError("Failed to create client run record")

        return client_run.id

    def _save_config_to_file(
        self,
        config: ConfigSchema,
        client_run_id: int,
    ) -> str:
        unique_id = str(uuid.uuid4())[:8]
        pipeline_dir = Path("config/pipeline")
        pipeline_dir.mkdir(parents=True, exist_ok=True)

        escaped_name = "".join(c if c.isalnum() else "_" for c in config.name)
        config_filename = f"agent_{escaped_name}_{unique_id}.yaml"
        config_path = pipeline_dir / config_filename

        with open(config_path, "w") as f:
            yaml.dump(config.content, f)

        logger.info(f"Saved config to {config_path} for client run {client_run_id}")
        return config_filename

    def _on_process_completed(self, run_id: int, exit_code: int) -> None:
        logger.info(
            f"Process completed callback for run {run_id} with exit code {exit_code}",
        )

        try:
            client_run = self.client_run_registry.get_by_id(run_id)

            if not client_run:
                logger.error(
                    f"Client run {run_id} not found in process completed callback",
                )
                return

            log_id = self.log_manager.collect_logs(run_id)
            logger.info(f"Collected logs for run {run_id}, log_id={log_id}")

            report_id = self.report_manager.generate_report(
                run_id,
            )
            logger.info(f"Generated report for run {run_id}, report_id={report_id}")

            self.client_run_registry.update(
                run_id,
                ClientRunUpdate(report_id=report_id),
            )

        except Exception:
            logger.exception(
                f"Unexpected error in process completed callback for run {run_id}",
            )

    def _start_process(
        self,
        config: ConfigSchema,
        client_run_id: int,
    ) -> ClientRunSchema:
        hydra_script_path = Path(self.hydra_script).resolve()
        if not hydra_script_path.is_file():
            raise FileNotFoundError(f"Hydra script not found: {hydra_script_path}")

        config_filename = self._save_config_to_file(config, client_run_id)
        config_name = config_filename.split(".")[0]

        run_output_dir = Path(self.outputs_dir) / str(client_run_id)
        ensure_dir_exists(run_output_dir)

        python_executable = "python"
        cmd = [
            python_executable,
            str(hydra_script_path),
            f"pipeline={config_name}",
            f"hydra.run.dir={run_output_dir}",
            "--config-name=agent",
        ]

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
                bufsize=1,
                universal_newlines=True,
            )

            client_run_update = ClientRunUpdate(
                pid=process.pid,
                status=RunStatus.RUNNING,
                output_dir=str(run_output_dir),
            )

            self.client_run_registry.update(client_run_id, client_run_update)
            client_run = self.client_run_registry.get_by_id(client_run_id)

            if not client_run:
                raise RuntimeError(f"Failed to retrieve client run: {client_run_id}")  # noqa: TRY301

            self.process_monitor.register_process(client_run_id, process)

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
            self.client_run_registry.update_run_status(client_run, RunStatus.STOPPED)
            updated_run = self.client_run_registry.get_by_id(run_id)

            if not updated_run:
                raise RuntimeError(  # noqa: TRY301
                    f"Failed to retrieve client run after stopping: {run_id}",
                )

        except ProcessLookupError as e:
            logger.warning(f"Process {client_run.pid} not found, marking as stopped")
            self.client_run_registry.update_run_status(client_run, RunStatus.STOPPED)

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
                self.client_run_registry.update_run_status(
                    client_run,
                    RunStatus.STOPPED,
                )
            return False
        except Exception:
            logger.exception(f"Error checking process status for run {run_id}")
            return False
        else:
            return True

    def get_process_output(self, run_id: int) -> dict[str, str]:
        return self.process_monitor.get_process_output(run_id)

    def is_process_running(self, run_id: int) -> bool:
        return self.process_monitor.is_process_running(run_id)

    def shutdown(self) -> None:
        """Stop the process monitor and clean up resources."""
        if hasattr(self, "process_monitor"):
            self.process_monitor.stop()
            logger.info("Process monitor stopped")
