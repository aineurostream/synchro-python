import logging
import queue
import select
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import IO, Any

from synchroagent.database.client_run_registry import ClientRunRegistry, ClientRunUpdate
from synchroagent.database.models import RunStatus

logger = logging.getLogger(__name__)


@dataclass
class ProcessInfo:
    run_id: int
    process: subprocess.Popen
    stdout_buffer: str = ""
    stderr_buffer: str = ""
    last_check_time: float = 0


ProcessCompletedCallback = Callable[[int, int], None]


class ClientProcessMonitor(threading.Thread):
    def __init__(
        self,
        client_run_registry: ClientRunRegistry,
        poll_interval: float = 1.0,
    ) -> None:
        """Initialize the process monitor.

        Args:
            client_run_registry: Registry for client runs
            poll_interval: How often to check processes (seconds)
        """
        super().__init__(daemon=True, name="ProcessMonitor")
        self.client_run_registry = client_run_registry
        self.poll_interval = poll_interval
        self.processes: dict[int, ProcessInfo] = {}
        self.process_queue: queue.Queue[ProcessInfo] = queue.Queue()
        self.running = True
        self.lock = threading.RLock()
        self.completed_outputs: dict[int, dict[str, str]] = {}

        self.on_process_completed: ProcessCompletedCallback | None = None

    def register_process(self, run_id: int, process: subprocess.Popen) -> None:
        with self.lock:
            self.process_queue.put(
                ProcessInfo(
                    run_id=run_id,
                    process=process,
                    last_check_time=time.time(),
                ),
            )
            logger.info(
                "Registered process for monitoring: run_id=%d, pid=%d",
                run_id,
                process.pid,
            )

    def set_process_completed_callback(
        self,
        callback: ProcessCompletedCallback,
    ) -> None:
        self.on_process_completed = callback

    def stop(self) -> None:
        self.running = False

    def run(self) -> None:
        logger.info("Process monitor started")

        while self.running:
            self._check_new_processes()

            with self.lock:
                for run_id, process_info in list(self.processes.items()):
                    try:
                        self._monitor_process(process_info)
                    except Exception:
                        logger.exception("Error monitoring process %d", run_id)

            time.sleep(self.poll_interval)

        logger.info("Process monitor stopped")

    def _check_new_processes(self) -> None:
        try:
            while True:
                process_info = self.process_queue.get_nowait()
                with self.lock:
                    self.processes[process_info.run_id] = process_info
                logger.debug(
                    f"Added process to monitoring: run_id={process_info.run_id}",
                )
                self.process_queue.task_done()
        except queue.Empty:
            pass

    def _monitor_process(self, process_info: ProcessInfo) -> None:
        exit_code = process_info.process.poll()

        self._read_process_output(process_info)

        if exit_code is not None:
            self._store_process_outputs(process_info)
            self._handle_process_exit(process_info, exit_code)

            if self.on_process_completed:
                run_id = process_info.run_id
                try:
                    self.on_process_completed(run_id, exit_code)
                except Exception:
                    logger.exception(
                        f"Error in process completed callback for run {run_id}",
                    )

            del self.processes[process_info.run_id]

    def _read_process_output(self, process_info: ProcessInfo) -> None:
        """Read available output from process stdout/stderr.

        Args:
            process_info: Information about the process
        """

        if process_info.process.stdout:
            output = self._read_pipe_nonblocking(process_info.process.stdout)
            if output:
                process_info.stdout_buffer += output

                logger.debug(f"STDOUT for run {process_info.run_id}: {output}")

        if process_info.process.stderr:
            output = self._read_pipe_nonblocking(process_info.process.stderr)
            if output:
                process_info.stderr_buffer += output

                logger.debug(f"STDERR for run {process_info.run_id}: {output}")

    def _read_pipe_nonblocking(self, pipe: IO[Any]) -> str:
        output = ""
        try:
            if select.select([pipe], [], [], 0)[0]:
                data = pipe.read()
                if data:
                    output = data
        except Exception:
            logger.exception("Error reading from pipe")

        return output

    def _store_process_outputs(self, process_info: ProcessInfo) -> None:
        run_id = process_info.run_id

        self.completed_outputs[run_id] = {
            "stdout": process_info.stdout_buffer,
            "stderr": process_info.stderr_buffer,
        }

        logger.info(f"Stored outputs for run {run_id}")

    def _handle_process_exit(self, process_info: ProcessInfo, exit_code: int) -> None:
        run_id = process_info.run_id
        logger.info(f"Process for run {run_id} exited with code {exit_code}")

        status = RunStatus.STOPPED if exit_code == 0 else RunStatus.FAILED
        try:
            self.client_run_registry.update(
                run_id,
                ClientRunUpdate(
                    status=status,
                    exit_code=exit_code,
                ),
            )
        except Exception:
            logger.exception("Error updating run status for %d", run_id)

    def get_process_output(self, run_id: int) -> dict[str, str]:
        with self.lock:
            if run_id in self.completed_outputs:
                return self.completed_outputs[run_id]
            if run_id in self.processes:
                process_info = self.processes[run_id]
                return {
                    "stdout": process_info.stdout_buffer,
                    "stderr": process_info.stderr_buffer,
                }

            return {"stdout": "", "stderr": ""}

    def is_process_running(self, run_id: int) -> bool:
        with self.lock:
            return run_id in self.processes
