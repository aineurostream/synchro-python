#!/usr/bin/env python3
import fcntl
import json
import logging
import os
import shlex
import signal
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from enum import StrEnum
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import FrameType
from typing import TextIO

import psutil
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

BIN = "hydra_run.py"
NAME = "synchro-agent"
LOCKFILE_PATH = str(Path(tempfile.gettempdir()) / f"{NAME}.lock")

# faster whisper input languages
LANGUAGES = [
    "af",
    "am",
    "ar",
    "as",
    "az",
    "ba",
    "be",
    "bg",
    "bn",
    "bo",
    "br",
    "bs",
    "ca",
    "cs",
    "cy",
    "da",
    "de",
    "el",
    "en",
    "es",
    "et",
    "eu",
    "fa",
    "fi",
    "fo",
    "fr",
    "gl",
    "gu",
    "ha",
    "haw",
    "he",
    "hi",
    "hr",
    "ht",
    "hu",
    "hy",
    "id",
    "is",
    "it",
    "ja",
    "jw",
    "ka",
    "kk",
    "km",
    "kn",
    "ko",
    "la",
    "lb",
    "ln",
    "lo",
    "lt",
    "lv",
    "mg",
    "mi",
    "mk",
    "ml",
    "mn",
    "mr",
    "ms",
    "mt",
    "my",
    "ne",
    "nl",
    "nn",
    "no",
    "oc",
    "pa",
    "pl",
    "ps",
    "pt",
    "ro",
    "ru",
    "sa",
    "sd",
    "si",
    "sk",
    "sl",
    "sn",
    "so",
    "sq",
    "sr",
    "su",
    "sv",
    "sw",
    "ta",
    "te",
    "tg",
    "th",
    "tk",
    "tl",
    "tr",
    "tt",
    "uk",
    "ur",
    "uz",
    "vi",
    "yi",
    "yo",
    "zh",
    "yue",
]

# basic logging
LOG_LEVEL = logging.INFO
logger = logging.getLogger(NAME)
logger.setLevel(LOG_LEVEL)
logger.propagate = False  # important — otherwise duplication to root logger

# --- format ---
fmt = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# --- file ---
file_handler = RotatingFileHandler(
    Path(f"{NAME}.log"),
    maxBytes=1024 * 1024,
    backupCount=0,
)
file_handler.setLevel(LOG_LEVEL)
file_handler.setFormatter(fmt)

# --- stdout ---
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setLevel(LOG_LEVEL)
stream_handler.setFormatter(fmt)

# --- final assembly ---
logger.handlers.clear()
logger.addHandler(file_handler)
logger.addHandler(stream_handler)

AGENT_HOST = os.environ.get("SYNCHRO_AGENT_HOST", "127.0.0.1")
AGENT_PORT = int(os.environ.get("SYNCHRO_AGENT_PORT", "50081"))


# --- guard against second process launch ---
def ensure_single_instance() -> TextIO:
    # Keep descriptor open for process lifetime to hold the file lock.
    lockfile = Path(LOCKFILE_PATH).open("w")  # noqa: SIM115
    try:
        fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        logger.warning("Daemon is already running")
        sys.exit(1)

    # don't close lockfile, otherwise the lock will be released
    return lockfile


# --- worker state ---
class WorkerState(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    STOPPING = "stopping"
    FINISHED = "finished"
    ERROR = "error"


class SpeakerParams(BaseModel):
    language: str | None = None
    gender: str = "M"
    voice: str = "Kumar Dahl"


class TranlationParams(BaseModel):
    language: str = "ru"


class SettingsParmas(BaseModel):
    server: str = "http://127.0.0.1:50080"

    config: str = "config"  # config
    ai: str = "default"  # config/ai
    pipeline: str = "default_file"
    name: str = "sample"

    audio_path: Path | None = Path(
        "/home/gof/Projects/volumes/samples/long/disabled_support_conference.wav",
    )
    run_time: int = 100

    playlist_path: str | None = None


class HydraParams(BaseModel):
    speakers: list[SpeakerParams]
    translations: list[TranlationParams]
    settings: SettingsParmas


class StopRequestedError(Exception):
    pass


app = FastAPI()

_task_lock = threading.Lock()  # single task instance


@dataclass
class AgentRuntime:
    worker_thread: threading.Thread | None = None
    stop_event: threading.Event = field(default_factory=threading.Event)
    state: WorkerState = WorkerState.IDLE
    last_error: str | None = None


_runtime = AgentRuntime()


def log_subprocess_line(raw_line: bytes | str, level: int = logging.INFO) -> None:
    # 1. Decode bytes
    if isinstance(raw_line, bytes):
        text = raw_line.decode("utf-8", errors="replace")
    else:
        text = raw_line
    text = text.rstrip("\r\n")

    # 2. Try to parse JSON
    try:
        data = json.loads(text)
        logger.log(
            level,
            "[subprocess] %s",
            json.dumps(data, indent=2, ensure_ascii=False),
        )
    except json.JSONDecodeError:
        # if it's not JSON — just write as-is
        logger.log(
            level,
            "[subprocess] %s",
            text,
        )
        return


def find_process_by_name(name: str) -> list[int]:
    """Find processes by name using psutil (cross-platform)."""
    pids = []
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        cmd = proc.info.get("cmdline")
        if cmd and name in cmd:
            pids.append(proc.pid)
        elif proc.status() == "zombie":
            logger.info("Found zombie process=%s; trying to kill", proc)
            os.kill(proc.pid, signal.SIGKILL)

    return pids


def stop_worker(name: str) -> None:
    logger.info("Trying to find and kill workers")
    pids = find_process_by_name(name)
    if pids:
        for pid in pids:
            os.kill(pid, signal.SIGTERM)
        logger.info("Send signal TERM to worker PIDS=%s", pids)
    else:
        logger.info("Running workers '%s' not found.", name)


def signal_handler(signum: int, _frame: FrameType | None) -> None:
    logger.info("Received signal %s; exiting", signum)
    stop_worker(BIN)

    logger.info("Terminate")
    sys.exit(0)


def _raise_stop_requested() -> None:
    raise StopRequestedError


def _build_worker_cmd(params: HydraParams) -> list[str]:
    if not params.speakers:
        msg = "At least one speaker is required"
        raise ValueError(msg)
    if not params.translations:
        msg = "At least one translation is required"
        raise ValueError(msg)

    voice_param = (
        f"{{{params.speakers[0].language}: ['xtts', '{params.speakers[0].voice}']}}"
    )
    return [
        x
        for x in [
            "uv",
            "run",
            "python",
            BIN,
            f"--config-name={params.settings.config}",
            f"ai={params.settings.ai}",
            f"ai.tts.voice_map={voice_param}",
            f"pipeline={params.settings.pipeline}",
            f"pipeline.nodes.0.path={params.settings.audio_path}",
            f"pipeline.nodes.3.lang_from={params.speakers[0].language}",
            f"pipeline.nodes.3.lang_to={params.translations[0].language}",
            f"pipeline.nodes.3.server_url={params.settings.server}",
            f"settings.name={params.settings.name}",
            f"settings.limits.run_time_seconds={params.settings.run_time}",
        ]
        if x is not None
    ]


def _pump_worker_output(process: subprocess.Popen[bytes]) -> None:
    if process.stdout:
        line = process.stdout.readline()
        if line:
            log_subprocess_line(line, logging.INFO)
            return
    if not process.stdout and not process.stderr:
        time.sleep(0.1)
        return
    time.sleep(0.1)


def _run_worker_loop(
    process: subprocess.Popen[bytes],
    stop_event: threading.Event,
) -> None:
    while True:
        if stop_event.is_set():
            _raise_stop_requested()

        return_code = process.poll()
        if return_code is not None:
            logger.info(
                "Subprocess exited with code %s",
                return_code,
            )
            return

        _pump_worker_output(process)


def _stop_child_process(process: subprocess.Popen[bytes] | None) -> None:
    logger.info("Stop requested, sending SIGTERM to child...")
    if not process or process.poll() is not None:
        return
    try:
        process.send_signal(signal.SIGTERM)
        try:
            process.wait(timeout=10.0)
            logger.info(
                "Subprocess terminated gracefully with code %s",
                process.returncode,
            )
        except subprocess.TimeoutExpired:
            logger.warning("Subprocess did not exit, sending SIGKILL")
            process.kill()
            process.wait()
            logger.info(
                "Subprocess killed, returncode=%s",
                process.returncode,
            )
    except Exception:
        logger.exception(
            "Error while stopping subprocess %s",
            process,
        )


def worker(stop_event: threading.Event, params: HydraParams) -> None:
    _runtime.state = WorkerState.RUNNING
    _runtime.last_error = None

    logger.info("Worker started with params %s", params.model_dump())
    process: subprocess.Popen[bytes] | None = None

    try:
        stop_worker(BIN)
        cmd = _build_worker_cmd(params)

        process = subprocess.Popen(  # noqa: S603
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=False,
            start_new_session=True,
            bufsize=2 * 1024,
        )

        logger.info(
            "Subprocess started, cmd=%s, pid=%s",
            shlex.join(cmd),
            process.pid,
        )
        _run_worker_loop(process, stop_event)
        _runtime.state = WorkerState.FINISHED
    except StopRequestedError:
        _stop_child_process(process)
    except Exception as exc:
        _runtime.last_error = str(exc)
        _runtime.state = WorkerState.ERROR
        logger.exception("Worker crashed with unexpected error")
    finally:
        logger.info("Worker cleanup")
        _runtime.state = (
            _runtime.state
            if _runtime.state == WorkerState.ERROR
            else WorkerState.FINISHED
        )


@app.post("/start")
def start(params: HydraParams) -> dict[str, str]:
    # Release stale lock if previous worker finished
    if _task_lock.locked() and (
        not _runtime.worker_thread or not _runtime.worker_thread.is_alive()
    ):
        _task_lock.release()

    # prevent launching a second task
    if not _task_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Task already running")

    if _runtime.worker_thread and _runtime.worker_thread.is_alive():
        # just in case (we shouldn't reach here if the lock is held)
        raise HTTPException(status_code=409, detail="Worker already running")

    _runtime.stop_event = threading.Event()
    _runtime.worker_thread = threading.Thread(
        target=worker,
        args=(_runtime.stop_event, params),
        daemon=True,
    )
    _runtime.worker_thread.start()
    logger.info("Task started with %s", params.model_dump())

    return {
        "status": "started",
    }


@app.post("/stop")
def stop() -> dict[str, str | WorkerState]:
    if not _runtime.worker_thread or not _runtime.worker_thread.is_alive():
        raise HTTPException(status_code=409, detail="Worker not running")

    _runtime.state = WorkerState.STOPPING
    _runtime.stop_event.set()
    _runtime.worker_thread.join(timeout=10)
    if _task_lock.locked():
        _task_lock.release()
    logger.info("Task stopped")

    return {
        "status": "stop_requested",
        "state": _runtime.state,
    }


@app.get("/status")
def status() -> dict[str, WorkerState | bool | str | None]:
    running = _runtime.worker_thread.is_alive() if _runtime.worker_thread else False
    logger.info("Task is %s", "running" if running else "stopped")

    return {
        "state": _runtime.state,
        "running": running,
        "error": _runtime.last_error,
    }


@app.post("/terminate")
def terminate() -> None:
    pid = os.getpid()
    logger.info("Agent PID=%s", pid)

    os.kill(pid, signal.SIGTERM)


def main() -> None:
    logger.info("Initialization")

    # ensure single daemon instance
    ensure_single_instance()

    uvicorn.run(
        "synchroagent.simple:app",
        host=AGENT_HOST,
        port=AGENT_PORT,
        reload=False,
    )

    logger.info("Server started...")


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    main()
