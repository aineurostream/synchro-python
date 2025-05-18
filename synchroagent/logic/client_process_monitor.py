import json
import logging
import os
import queue
import select
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import IO

from synchroagent.database.client_run_registry import ClientRunRegistry, ClientRunUpdate
from synchroagent.database.models import RunStatus
from synchroagent.logic.event_bus import event_bus
from synchroagent.schemas import LogEventSchema

logger = logging.getLogger(__name__)


@dataclass
class ProcessInfo:
    run_id: int
    process: subprocess.Popen
    stdout_buffer: bytes = b""
    stderr_buffer: bytes = b""
    last_check_time: float = 0


ProcessCompletedCallback = Callable[[int, int], None]


class ClientProcessMonitor(threading.Thread):
    def __init__(
        self,
        client_run_registry: ClientRunRegistry,
        poll_interval: float = 0.016,
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
        self.completed_outputs: dict[int, dict[str, bytes]] = {}

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
                        logger.debug(f"Monitoring process {run_id}")
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
            logger.debug(f"Process {process_info.run_id} exit code: {exit_code}")
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
        stdout_pipe = process_info.process.stdout
        if stdout_pipe:
            try:
                output_bytes = self._read_pipe_nonblocking(stdout_pipe)
                if output_bytes:
                    process_info.stdout_buffer += output_bytes
                    logger.debug(
                        (
                            f"Read {len(output_bytes)} bytes from STDOUT for run "
                            f"{process_info.run_id}",
                        ),
                    )
            except Exception:
                logger.exception(
                    f"Error during stdout processing for run {process_info.run_id}",
                )

        stderr_pipe = process_info.process.stderr
        if stderr_pipe:
            try:
                output_bytes = self._read_pipe_nonblocking(stderr_pipe)
                if output_bytes:
                    process_info.stderr_buffer += output_bytes
                    logger.debug(
                        (
                            f"Read {len(output_bytes)} bytes from STDERR for run "
                            f"{process_info.run_id}",
                        ),
                    )
            except Exception:
                logger.exception(
                    f"Error during stderr processing for run {process_info.run_id}",
                )

        self._parse_and_emit_log_lines(process_info, "stdout")
        self._parse_and_emit_log_lines(process_info, "stderr")

    def _read_pipe_nonblocking(self, pipe: IO[bytes]) -> bytes:
        """Read available data from the pipe without blocking. Returns raw bytes."""
        data = b""
        try:
            if pipe.fileno() != -1 and select.select([pipe], [], [], 0.0)[0]:
                chunk = os.read(pipe.fileno(), 16 * 1024)
                data = chunk
        except (BlockingIOError, InterruptedError):
            pass
        except BrokenPipeError:
            logger.warning(f"Broken pipe when reading from fd {pipe.fileno()}")
        except ValueError:
            logger.warning(f"Attempted to read from closed pipe fd {pipe.fileno()}")
        except Exception:
            logger.exception(f"Error reading from pipe fd {pipe.fileno()}")
        return data

    def _parse_and_emit_log_lines(
        self,
        process_info: ProcessInfo,
        stream_type: str,
    ) -> None:
        buffer_attr = f"{stream_type}_buffer"
        current_buffer: bytes = getattr(process_info, buffer_attr)

        processed_buffer = bytearray()  # To store lines that are processed

        temp_buffer = current_buffer
        lines_found = False

        while b"\n" in temp_buffer:
            lines_found = True
            line_bytes, temp_buffer = temp_buffer.split(b"\n", 1)
            processed_buffer.extend(line_bytes + b"\n")

            try:
                line_str = line_bytes.decode("utf-8").strip()
                if not line_str:
                    continue
                logger.debug(f"Processing line: {line_str[:100]}")
                log_content_dict = json.loads(line_str)
                event_bus.emit(
                    LogEventSchema(
                        run_id=process_info.run_id,
                        log_type=stream_type,
                        content=log_content_dict,
                    ),
                )
                logger.debug(
                    (
                        f"{stream_type.upper()} for run {process_info.run_id} "
                        f"(parsed): {str(log_content_dict)[:100]}...",
                    ),
                )
            except Exception:
                logger.exception(
                    (
                        f"Unexpected error parsing log line from {stream_type} for run "
                        f"{process_info.run_id}",
                    ),
                )

        if lines_found:
            setattr(process_info, buffer_attr, temp_buffer)

    def _store_process_outputs(self, process_info: ProcessInfo) -> None:
        run_id = process_info.run_id
        self._parse_and_emit_log_lines(process_info, "stdout")
        self._parse_and_emit_log_lines(process_info, "stderr")
        self.completed_outputs[run_id] = {
            "stdout": process_info.stdout_buffer,
            "stderr": process_info.stderr_buffer,
        }

        logger.info(f"Stored byte outputs for run {run_id}")

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
            stdout_str = ""
            stderr_str = ""

            if run_id in self.completed_outputs:
                stdout_bytes = self.completed_outputs[run_id].get("stdout", b"")
                stderr_bytes = self.completed_outputs[run_id].get("stderr", b"")
                stdout_str = stdout_bytes.decode("utf-8", errors="replace")
                stderr_str = stderr_bytes.decode("utf-8", errors="replace")
            elif run_id in self.processes:
                process_info = self.processes[run_id]
                stdout_str = process_info.stdout_buffer.decode(
                    "utf-8",
                    errors="replace",
                )
                stderr_str = process_info.stderr_buffer.decode(
                    "utf-8",
                    errors="replace",
                )

            return {"stdout": stdout_str, "stderr": stderr_str}

    def is_process_running(self, run_id: int) -> bool:
        with self.lock:
            return run_id in self.processes
