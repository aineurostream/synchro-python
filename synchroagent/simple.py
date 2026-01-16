#!/usr/bin/env python3
import json
import fcntl
import os
import sys
import threading
import time
import signal
import shlex
import logging
import subprocess
from logging.handlers import RotatingFileHandler
from pathlib import Path
from enum import Enum
from typing import Literal

import psutil
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


BIN = "hydra_run.py"
NAME = "synchro-agent"
LOCKFILE_PATH = f"/tmp/{NAME}.lock"

# faster whisper input languages
LANGUAGES = [
    "af", "am", "ar", "as", "az", 
    "ba", "be", "bg", "bn", "bo", "br", "bs", 
    "ca", "cs", "cy", 
    "da", "de", 
    "el", "en", "es", "et", "eu", 
    "fa", "fi", "fo", "fr", 
    "gl", "gu", 
    "ha", "haw", "he", "hi", "hr", "ht", "hu", "hy", "id", 
    "is", "it", 
    "ja", "jw", 
    "ka", "kk", "km", "kn", "ko", 
    "la", "lb", "ln", "lo", "lt", "lv", 
    "mg", "mi", "mk", "ml", "mn", "mr", "ms", "mt", "my", 
    "ne", "nl", "nn", "no", 
    "oc", 
    "pa", "pl", "ps", "pt", 
    "ro", "ru", 
    "sa", "sd", "si", "sk", "sl", "sn", "so", "sq", "sr", "su", "sv", "sw", 
    "ta", "te", "tg", "th", "tk", "tl", "tr", "tt", 
    "uk", "ur", "uz", 
    "vi", 
    "yi", "yo", 
    "zh", 
    "yue",
]

# basic logging
LOG_LEVEL = logging.INFO
logger = logging.getLogger(NAME)
logger.setLevel(LOG_LEVEL)
logger.propagate = False  # важно — иначе дублирование в корневой логгер

# --- формат ---
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

# --- финальная сборка ---
logger.handlers.clear()
logger.addHandler(file_handler)
logger.addHandler(stream_handler)


# --- защита от второго запуска процесса ---
def ensure_single_instance():
    lockfile = open(LOCKFILE_PATH, "w")
    try:
        fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        logger.warning("Daemon is already running", file=sys.stderr)
        sys.exit(1)
        
    # не закрываем lockfile, иначе лок снимется
    return lockfile


# --- состояние воркера ---
class WorkerState(str, Enum):
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
    ai: str = "bioprom"  # config/ai
    # pipeline: str = "2510_postbioprom_sample"  # config/pipeline
    pipeline: str = "december_sample"
    name: str = "sample"

    audio_path: Path | None = "/home/gof/Projects/volumes/samples/long/disabled_support_conference.wav"
    run_time: int = 100

    playlist_path: str | None = None


class HydraParams(BaseModel):
    speakers: list[SpeakerParams]
    translations: list[TranlationParams]
    settings: SettingsParmas
    

class StopRequested(Exception):
    pass


app = FastAPI()

_worker_thread: threading.Thread | None = None
_stop_event = threading.Event()
_state = WorkerState.IDLE
_last_error: str | None = None
_task_lock = threading.Lock()  # один инстанс задачи


def log_subprocess_line(raw_line: bytes | str, level: int = logging.INFO) -> None:
    # 1. Декодируем байты
    if isinstance(raw_line, bytes):
        text = raw_line.decode("utf-8", errors="replace")
    else:
        text = raw_line
    text = text.rstrip("\r\n")

    # 2. Пытаемся распарсить JSON
    try:
        data = json.loads(text)
        logger.log(
            level,
            "[subprocess] %s", 
            json.dumps(data, indent=2, ensure_ascii=False),
        )
    except json.JSONDecodeError:
        # если это не JSON — просто пишем как есть
        logger.log(
            level, 
            "[subprocess] %s", 
            text,
        )
        return
    

def find_process_by_name(name):
    """Find processes by name using psutil (cross-platform)."""
    pids = []
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        cmd = proc.info.get("cmdline")
        if cmd and name in cmd:
            pids.append(proc.pid)
        elif proc.status == "zombie":
            logger.info("Found zombie process=%s; trying to kill", proc)
            os.kill(proc.pid, signal.SIGKILL)

    return pids


def stop_worker(name):
    logger.info("Trying to find and kill workers")
    pids = find_process_by_name(name)
    if pids:
        [os.kill(x, signal.SIGTERM) for x in pids] 
        logger.info("Send signal TERM to worker PIDS=%s", pids)
    else:
        logger.info("Running workers '%s' not found.", name)


def signal_handler(signum, frame):
    logger.info(f"Received signal {signum}; exiting")
    stop_worker(BIN)
    
    logger.info("Terminate")
    exit(0)


def worker(stop_event, params: HydraParams):
    global _state, _last_error
    _state = WorkerState.RUNNING
    _last_error = None

    logger.info("Worker started with params %s", params.model_dump())
    process = None
    
    try:
        stop_worker(BIN)

        voice_param = (
            f"{{{params.speakers[0].language}: ['xtts', '{params.speakers[0].voice}']}}" 
            if params.speakers else 
            None
        )

        cmd = [x for x in [
            "uv", "run", "python", BIN,
            f"--config-name={params.settings.config}",
            f"ai={params.settings.ai}",
            f"ai.tts.voice_map={voice_param}",
            # f"stt.buffer_min_words_size={params.settings}",
            # f"stt.buffer_timeout_seconds={params.settings}",
            f"pipeline={params.settings.pipeline}",
            f"pipeline.nodes.0.path={params.settings.audio_path}",
            f"pipeline.nodes.3.lang_from={params.speakers[0].language}",
            f"pipeline.nodes.3.lang_to={params.translations[0].language}",
            f"pipeline.nodes.3.server_url={params.settings.server}",
            f"settings.name={params.settings.name}",
            f"settings.limits.run_time_seconds={params.settings.run_time}",
        ] if x is not None]

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=False,
            start_new_session=True,
            bufsize=2 * 1024,
        )

        logger.info(
            "Subprocess started, cmd=%s, pid=%s", 
            shlex.join(cmd), process.pid,
        )

        while True:
            # 1) проверка на запрос остановки
            if stop_event.is_set():
                raise StopRequested()

            # 2) проверка, не завершился ли процесс сам
            return_code = process.poll()
            if return_code is not None:
                logger.info(
                    "Subprocess exited with code %s", 
                    return_code,
                )
                break

            # 3) опционально читаем строки из stdout
            if process.stdout:
                line = process.stdout.readline()
                if line:
                    log_subprocess_line(line, logging.INFO)
                else:
                    # если ничего нет — маленький sleep, чтобы не крутить CPU
                    time.sleep(0.1)
            
            if not process.stdout and not process.stderr:
                time.sleep(0.1)

        _state = WorkerState.FINISHED
    except StopRequested:
        logger.info("Stop requested, sending SIGTERM to child...")
        if process and process.poll() is None:
            try:
                process.send_signal(signal.SIGTERM)
                # ждём аккуратного завершения
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
                        process.returncode
                    )
            except Exception:
                logger.exception(
                    "Error while stopping subprocess %s", 
                    process,
                )
    except Exception as exc:
        _last_error = str(exc)
        _state = WorkerState.ERROR
        logger.exception("Worker crashed with unexpected error")
    finally:
        logger.info("Worker cleanup")
        # отпускаем лок в любом случае
        if _task_lock.locked():
            _task_lock.release()


@app.post("/start")
def start(params: HydraParams):
    global _worker_thread, _stop_event, _state

    # не даём запустить вторую задачу
    if not _task_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Task already running")

    if _worker_thread and _worker_thread.is_alive():
        # на всякий случай (вообще до сюда не дойдём, если лок занят)
        raise HTTPException(status_code=409, detail="Worker already running")

    _stop_event = threading.Event()
    _worker_thread = threading.Thread(
        target=worker,
        args=(_stop_event, params),
        daemon=True,
    )
    _worker_thread.start()
    logger.info("Task started with %s", params.model_dump())

    return {
        "status": "started",
    }


@app.post("/stop")
def stop():
    global _worker_thread, _stop_event, _state

    if not _worker_thread or not _worker_thread.is_alive():
        raise HTTPException(status_code=409, detail="Worker not running")

    _state = WorkerState.STOPPING
    _stop_event.set()
    _worker_thread.join(timeout=10)
    logger.info("Task stopped")

    return {
        "status": "stop_requested", 
        "state": _state,
    }


@app.get("/status")
def status():
    running = _worker_thread.is_alive() if _worker_thread else False
    logger.info("Task is %s", "running" if running else "stopped")

    return {
        "state": _state,
        "running": running,
        "error": _last_error,
    }


@app.post("/terminate")
def terminate():
    pid = os.getpid()
    logger.info("Agent PID=%s", pid)

    os.kill(pid, signal.SIGTERM)


def main():
    logger.info("Initialization")

    # гарантируем один инстанс демона
    ensure_single_instance()

    uvicorn.run(
        f"synchroagent.simple:app",
        host="0.0.0.0",
        port=50081,
        reload=False,
    )

    logger.info("Server started...")


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    main()
