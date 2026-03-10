import logging
import os
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

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

WAIT_TIMEOUT_SECONDS = 10


def _raise_runtime(message: str) -> NoReturn:
    raise RuntimeError(message)


@dataclass(frozen=True)
class ProcessManagers:
    log_manager: LogManager
    report_manager: ReportManager


class ClientProcessManager:
    def __init__(
        self,
        client_registry: ClientRegistry,
        client_run_registry: ClientRunRegistry,
        config_registry: ConfigRegistry,
        process_managers: ProcessManagers,
        outputs_dir: str | None = None,
    ) -> None:
        self.client_registry = client_registry
        self.client_run_registry = client_run_registry
        self.config_registry = config_registry
        self.log_manager = process_managers.log_manager
        self.report_manager = process_managers.report_manager
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
            msg = f"Client not found: {client_id}"
            raise ValueError(msg)

        config = self.config_registry.get_by_id(config_id)
        if not config:
            msg = f"Configuration not found: {config_id}"
            raise ValueError(msg)

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
            msg = "Failed to create client run record"
            raise RuntimeError(msg)

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

        with config_path.open("w", encoding="utf-8") as f:
            yaml.dump(config.content, f)

        logger.info(
            "Saved config to %s for client run %s",
            config_path,
            client_run_id,
        )
        return config_filename

    def _on_process_completed(self, run_id: int, exit_code: int) -> None:
        logger.info(
            "Process completed callback for run %s with exit code %s",
            run_id,
            exit_code,
        )

        try:
            client_run = self.client_run_registry.get_by_id(run_id)

            if not client_run:
                logger.error(
                    "Client run %s not found in process completed callback",
                    run_id,
                )
                return

            log_id = self.log_manager.collect_logs(run_id)
            logger.info("Collected logs for run %s, log_id=%s", run_id, log_id)

            report = self.report_manager.generate_report(
                run_id,
            )
            logger.info(
                "Generated report for run %s, report_id=%s",
                run_id,
                report.id,
            )
        except Exception:
            logger.exception(
                "Unexpected error in process completed callback for run %s",
                run_id,
            )

    def _start_process(
        self,
        config: ConfigSchema,
        client_run_id: int,
    ) -> ClientRunSchema:
        hydra_script_path = Path(self.hydra_script).resolve()
        if not hydra_script_path.is_file():
            msg = f"Hydra script not found: {hydra_script_path}"
            raise FileNotFoundError(msg)

        config_filename = self._save_config_to_file(config, client_run_id)
        config_name = config_filename.split(".")[0]

        run_output_dir = Path(self.outputs_dir) / str(client_run_id)
        ensure_dir_exists(run_output_dir)

        python_executable = "python"
        cmd = [
            python_executable,
            "-u",
            str(hydra_script_path),
            f"pipeline={config_name}",
            f"hydra.run.dir={run_output_dir}",
            "--config-name=config",
        ]

        try:
            process = subprocess.Popen(  # noqa: S603
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False,
                start_new_session=True,
                bufsize=2 * 1024,
            )

            client_run_update = ClientRunUpdate(
                pid=process.pid,
                status=RunStatus.RUNNING,
                output_dir=str(run_output_dir),
            )

            self.client_run_registry.update(client_run_id, client_run_update)
            client_run = self.client_run_registry.get_by_id(client_run_id)

            if not client_run:
                msg = f"Failed to retrieve client run: {client_run_id}"
                _raise_runtime(msg)

            self.process_monitor.register_process(client_run_id, process)

            logger.info(
                "Started client run %s with PID %s",
                client_run_id,
                process.pid,
            )
        except Exception as e:
            self.client_run_registry.update_status(client_run_id, RunStatus.FAILED)
            logger.exception("Failed to start process for run %s", client_run_id)
            msg = f"Failed to start client process: {e}"
            raise RuntimeError(msg) from e
        else:
            return client_run

    def start_client(self, client_id: int, config_id: int) -> ClientRunSchema:
        try:
            _client, config = self._validate_client_and_config(client_id, config_id)
            client_run_id = self._create_client_run(client_id, config_id)
            return self._start_process(config, client_run_id)
        except Exception:
            logger.exception("Failed to start client %s", client_id)
            raise

    def stop_client_run(self, run_id: int) -> ClientRunSchema:
        client_run = self._get_running_run(run_id)
        try:
            self._create_stop_flag(client_run, run_id)
            self._wait_for_run_stop(run_id)
            self.client_run_registry.update_run_status(client_run, RunStatus.STOPPED)
            return self._get_run_or_raise(run_id)
        except ProcessLookupError:
            logger.warning(
                "Process %s not found, marking as stopped",
                client_run.pid,
            )
            self.client_run_registry.update_run_status(client_run, RunStatus.STOPPED)
            return self._get_run_or_raise(run_id)
        except Exception as e:
            logger.exception("Error stopping client run %s", run_id)
            msg = f"Failed to stop client run: {e}"
            raise RuntimeError(msg) from e

    def _get_running_run(self, run_id: int) -> ClientRunSchema:
        client_run = self.client_run_registry.get_by_id(run_id)
        if not client_run:
            msg = f"Client run not found: {run_id}"
            raise ValueError(msg)
        if client_run.status != RunStatus.RUNNING:
            msg = f"Client run is not running: {run_id}"
            raise ValueError(msg)
        if client_run.pid is None:
            msg = f"Client run has no process ID: {run_id}"
            raise ValueError(msg)
        return client_run

    def _create_stop_flag(self, client_run: ClientRunSchema, run_id: int) -> None:
        stop_flag_file = (
            Path(client_run.output_dir or "").resolve().joinpath("stop.flag")
        )
        stop_flag_file.touch()
        logger.info(
            "Created stop flag file at %s for client run %s",
            stop_flag_file.resolve().as_posix(),
            run_id,
        )

    def _wait_for_run_stop(self, run_id: int) -> None:
        wait_time: float = 0
        while self.check_process_status(run_id):
            logger.info("Waiting for client run %s to stop", run_id)
            time.sleep(0.1)
            wait_time += 0.1
            if wait_time > WAIT_TIMEOUT_SECONDS:
                msg = f"Client run {run_id} did not stop after 10 seconds"
                _raise_runtime(msg)

    def _get_run_or_raise(self, run_id: int) -> ClientRunSchema:
        updated_run = self.client_run_registry.get_by_id(run_id)
        if not updated_run:
            msg = f"Failed to retrieve client run after stopping: {run_id}"
            _raise_runtime(msg)
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
            logger.exception("Error checking process status for run %s", run_id)
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
