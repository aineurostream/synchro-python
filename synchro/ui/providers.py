from __future__ import annotations

import logging
import os
import time
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Lock, Thread
from typing import TYPE_CHECKING, Any

from hydra import compose, initialize_config_dir

from synchro.config.schemas import (
    ProcessingGraphConfig,
    SeamlessConnectorNodeSchema,
)
from synchro.config.settings import SettingsSchema
from synchro.graph.graph_initializer import GraphInitializer
from synchro.graph.graph_manager import GraphManager
from synchroagent.utils import get_datetime_iso

if TYPE_CHECKING:
    from omegaconf import DictConfig

    from synchro.config.commons import NodeEventsCallback
    from synchro.ui.settings import UISettings

try:
    import sounddevice as sd  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - optional at runtime
    sd = None


_START_TS = time.time()
_MAX_BUFFER_LINES = 2000
_TRIM_TO_LINES = 1000


@dataclass
class DeviceInfo:
    name: str
    max_input_channels: int
    max_output_channels: int
    default_samplerate: float
    device_id: int


def _enumerate_devices() -> list[DeviceInfo]:
    devices: list[DeviceInfo] = []
    if sd is None:
        return devices
    try:
        for i, d in enumerate(sd.query_devices()):  # type: ignore[call-arg]
            devices.append(
                DeviceInfo(
                    name=d["name"],
                    max_input_channels=d["max_input_channels"],
                    max_output_channels=d["max_output_channels"],
                    default_samplerate=float(d["default_samplerate"]),
                    device_id=i,
                ),
            )
    except (AttributeError, OSError, RuntimeError):
        logging.getLogger(__name__).exception("Failed to enumerate audio devices")
    return devices


def list_input_devices() -> list[DeviceInfo]:
    return [d for d in _enumerate_devices() if d.max_input_channels > 0]


def list_output_devices() -> list[DeviceInfo]:
    return [d for d in _enumerate_devices() if d.max_output_channels > 0]


def get_preset_filters() -> list[str]:
    """Preset filters for model logs column."""
    return [
        "all",
        "translation",
        "transcription",
        "correction",
        "errors",
    ]


def get_model_logs(_active_filter: str) -> list[str]:
    """Legacy shim; prefer using app-managed fetchers."""
    ts = get_datetime_iso()
    base: list[str] = [
        f"{ts} | info | no stream",
    ]
    return base


def get_system_logs() -> list[str]:
    ts = get_datetime_iso()
    return [
        f"{ts} | INFO | Synchro starting",
        f"{ts} | INFO | Waiting for configuration",
    ]


def get_system_info() -> dict[str, Any]:
    """Return simple system info.

    This does not compute real node state; it demonstrates shape and
    calls a shared util for time formatting.
    """
    uptime_sec = max(0, int(time.time() - _START_TS))
    return {
        "uptime": uptime_sec,
        "uptime_iso": get_datetime_iso(),  # last refresh time
        "nodes": [
            {"name": "input_mic", "state": "running"},
            {"name": "converter", "state": "running"},
            {"name": "output", "state": "running"},
        ],
        # App overlays `audio_active` depending on running sources
        "audio_active": False,
    }


def get_initial_config_from_env() -> dict[str, Any] | None:
    """Backward-compatible shim; prefer using UISettings in `synchro.ui.settings`."""
    input_device = os.getenv("INPUT_DEVICE")
    output_device = os.getenv("OUTPUT_DEVICE")
    lang_from = os.getenv("LANG_FROM")
    lang_to = os.getenv("LANG_TO")
    tts_engine = os.getenv("TTS_ENGINE")
    if not (input_device and output_device and lang_from and lang_to and tts_engine):
        return None
    return {
        "input_device": int(input_device),
        "output_device": int(output_device),
        "lang_from": lang_from,
        "lang_to": lang_to,
        "tts_engine": tts_engine,
    }


# ----- Live log stream over existing websocket connector -----


class _BufferHandler(logging.Handler):
    def __init__(self, sink: list[str], lock: Lock) -> None:
        super().__init__()
        self._sink = sink
        self._lock = lock

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        with self._lock:
            self._sink.append(msg)
            if len(self._sink) > _MAX_BUFFER_LINES:
                del self._sink[:_TRIM_TO_LINES]


class LogStream:
    def __init__(self, server_url: str, lang_from: str, lang_to: str) -> None:
        self._logger = logging.getLogger(__name__ + ".LogStream")
        self.server_url = server_url
        self.lang_from = lang_from
        self.lang_to = lang_to
        self._thread: Thread | None = None
        self._stop = Event()
        self._lock = Lock()
        self._lines: list[tuple[str, str]] = []  # (tag, line)
        self._gm: GraphManager | None = None
        self._sys_lines: list[str] = []
        self._handler = _BufferHandler(self._sys_lines, self._lock)
        self._handler.setLevel(logging.INFO)
        self._logger.addHandler(self._handler)
        self._logger.setLevel(logging.INFO)
        self._ever_started = False

    def _events_cb(self, _node_name: str, log: dict) -> None:
        try:
            ctx = log.get("context", {})
            action = str(ctx.get("action") or ctx.get("part") or "info")
            message = str(ctx.get("message") or ctx.get("text") or "")
            ts = get_datetime_iso()
            tag = action.lower()
            # Normalize tags for filters
            if tag.startswith("transcription"):
                tag = "transcription"
            elif tag.startswith("translation"):
                tag = "translation"
            elif tag.startswith("correction"):
                tag = "correction"
            # Heuristic for errors
            if "error" in message.lower() or ctx.get("sub_action") == "fail":
                tag = "errors"
            line = f"{ts} | {tag} | {message}"
            with self._lock:
                self._lines.append((tag, line))
            # Mirror to stdout logs for visibility
            level = logging.ERROR if tag == "errors" else logging.INFO
            self._logger.log(level, line)
            # Prevent unbounded growth
            if len(self._lines) > _MAX_BUFFER_LINES:
                self._lines = self._lines[-_TRIM_TO_LINES:]
        except (AttributeError, KeyError, TypeError, ValueError):
            # Swallow logging exceptions to not break UI
            self._logger.exception("Failed to process event callback")

    def start(self) -> bool:
        if (self._thread and self._thread.is_alive()) or self._ever_started:
            return False
        # Build minimal graph with SeamlessConnectorNode only
        seam_cfg = SeamlessConnectorNodeSchema(
            name="ui_connector",
            server_url=self.server_url,
            lang_from=self.lang_from,
            lang_to=self.lang_to,
        )
        proc_cfg = ProcessingGraphConfig(nodes=[seam_cfg], edges=[])
        settings = SettingsSchema(
            name="ui",
            input_interval_secs=0.3,
            processor_interval_secs=0.05,
        )
        events_cb: NodeEventsCallback = self._events_cb  # type: ignore[assignment]
        self._stop.clear()

        def _runner() -> None:
            try:
                with self._lock:
                    self._lines.append(("info", f"connecting to {self.server_url}"))
                self._logger.info("Connecting to %s", self.server_url)
                nodes, edges = GraphInitializer(
                    settings=settings,
                    config=proc_cfg,
                    neuro_config={},
                    events_cb=events_cb,
                    working_dir=None,
                ).build()
                gm = GraphManager(nodes, edges, settings)
                self._gm = gm
                # Run until stop() is called
                gm.execute()
            except Exception:
                # Record a line for visibility
                with self._lock:
                    self._lines.append(("errors", "connection closed"))
                self._logger.exception("Log stream terminated with error")

        self._ever_started = True
        self._thread = Thread(target=_runner, name="LogStream", daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop.set()
        if self._gm is not None:
            with suppress(RuntimeError, OSError):
                self._gm.stop()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None
        self._gm = None
        self._ever_started = False

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def get_logs_filtered(self, active_filter: str) -> list[str]:
        with self._lock:
            if active_filter == "all":
                return [line for _tag, line in self._lines[-500:]]
            return [line for tag, line in self._lines[-500:] if tag == active_filter]

    def get_system_log_lines(self) -> list[str]:
        with self._lock:
            return list(self._sys_lines[-500:])


_LOG_STREAM: LogStream | None = None


class PipelineRunner:
    def __init__(self, settings: UISettings) -> None:
        self._settings = settings
        self._thread: Thread | None = None
        self._stop = Event()
        self._lock = Lock()
        self._gm: GraphManager | None = None
        self._lines: list[tuple[str, str]] = []
        self._logger = logging.getLogger(__name__ + ".Pipeline")

    def _events_cb(self, _node_name: str, log: dict) -> None:
        # Reuse same formatting as _LogStream
        try:
            ctx = log.get("context", {})
            action = str(ctx.get("action") or ctx.get("part") or "info")
            message = str(ctx.get("message") or ctx.get("text") or "")
            ts = get_datetime_iso()
            tag = action.lower()
            if tag.startswith("transcription"):
                tag = "transcription"
            elif tag.startswith("translation"):
                tag = "translation"
            elif tag.startswith("correction"):
                tag = "correction"
            if "error" in message.lower() or ctx.get("sub_action") == "fail":
                tag = "errors"
            line = f"{ts} | {tag} | {message}"
            with self._lock:
                self._lines.append((tag, line))
                if len(self._lines) > _MAX_BUFFER_LINES:
                    self._lines = self._lines[-_TRIM_TO_LINES:]
            level = logging.ERROR if tag == "errors" else logging.INFO
            self._logger.log(level, line)
        except (AttributeError, KeyError, TypeError, ValueError):
            self._logger.exception("Failed to process pipeline event")

    def _mutate_cfg(self, cfg: DictConfig) -> DictConfig:
        # Override pipeline nodes and ai according to UI settings
        pipeline = cfg.get("pipeline")
        ai = cfg.get("ai")
        settings = cfg.get("settings")

        self._apply_pipeline_overrides(pipeline)
        self._apply_tts_override(cfg, ai)
        self._ensure_unlimited_runtime(cfg, settings)
        return cfg

    def _apply_pipeline_overrides(self, pipeline: dict | None) -> None:
        # Override input/output devices
        nodes = pipeline.get("nodes", []) if pipeline else []
        for n in nodes:
            nt = str(n.get("node_type"))
            if nt == "input_channel" and self._settings.input_device is not None:
                n["device"] = int(self._settings.input_device)
            if nt == "output_channel" and self._settings.output_device is not None:
                n["device"] = int(self._settings.output_device)
            if nt == "converter_seamless":
                if self._settings.lang_from:
                    n["lang_from"] = self._settings.lang_from
                if self._settings.lang_to:
                    n["lang_to"] = self._settings.lang_to
                if self._settings.converter_server:
                    n["server_url"] = self._settings.converter_server

    def _apply_tts_override(self, cfg: DictConfig, ai: dict | None) -> None:
        # Override TTS engine (if structure exists)
        if ai is None:
            cfg["ai"] = {}
            ai = cfg["ai"]
        tts = ai.get("tts") if isinstance(ai, dict) else None
        if tts is None:
            ai["tts"] = {}
            tts = ai["tts"]
        if self._settings.tts_engine:
            tts["engine"] = self._settings.tts_engine

    def _ensure_unlimited_runtime(
        self,
        cfg: DictConfig,
        settings: dict | None,
    ) -> None:
        # Ensure unlimited run time inside UI
        if settings is None:
            cfg["settings"] = {}
            settings = cfg["settings"]
        limits = settings.get("limits") if isinstance(settings, dict) else None
        if limits is None:
            settings["limits"] = {}
            limits = settings["limits"]
        limits["run_time_seconds"] = 0

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        def _runner() -> None:
            try:
                self._logger.info(
                    "Starting pipeline: base=%s",
                    self._settings.base_config_name,
                )
                # Resolve project root (directory that contains 'config/config.yaml')
                config_dir = self._resolve_config_dir()
                self._logger.info("Using config dir: %s", config_dir.as_posix())
                with initialize_config_dir(
                    version_base=None,
                    config_dir=str(config_dir),
                ):
                    cfg = compose(config_name=self._settings.base_config_name)
                cfg = self._mutate_cfg(cfg)
                # Convert to Pydantic models as in hydra_run
                from hydra_run import initialize_configs  # noqa: PLC0415

                core_config, settings_model, neural_config_dict = initialize_configs(
                    cfg,
                )
                nodes, edges = GraphInitializer(
                    settings_model,
                    core_config,
                    neural_config_dict,
                    self._events_cb,
                    None,
                ).build()
                gm = GraphManager(nodes, edges, settings_model)
                self._gm = gm
                gm.execute()
            except Exception as e:
                # Log and store a human-friendly message
                self._logger.exception("Pipeline terminated with error")
                with self._lock:
                    self._lines.append(("errors", f"pipeline error: {e!s}"))

        self._thread = Thread(target=_runner, name="PipelineRunner", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._gm is not None:
            try:
                self._gm.stop()
            except (RuntimeError, OSError):
                self._logger.exception("Failed to stop graph manager")
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None
        self._gm = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def get_logs_filtered(self, active_filter: str) -> list[str]:
        with self._lock:
            if active_filter == "all":
                return [line for _tag, line in self._lines[-500:]]
            return [line for tag, line in self._lines[-500:] if tag == active_filter]

    def _resolve_config_dir(self) -> Path:
        """Find absolute path to the 'config' directory from anywhere in the repo.

        Walks up from this file location until it finds a directory that
        contains 'config/config.yaml'. Falls back to current working directory
        joined with 'config'.
        """
        here = Path(__file__).resolve()
        for parent in [here, *list(here.parents)]:
            candidate = parent / ".."  # bias towards project root above 'synchro'
            for base in [parent, candidate.resolve()]:
                cfg = base / "config" / "config.yaml"
                if cfg.exists():
                    return (base / "config").resolve()
        cwd_candidate = Path.cwd() / "config"
        return cwd_candidate.resolve()


def start_log_stream(server_url: str, lang_from: str, lang_to: str) -> LogStream:
    """Factory for app-managed log stream (no globals)."""
    stream = LogStream(server_url, lang_from, lang_to)
    stream.start()
    return stream


def stop_log_stream(stream: LogStream | None) -> None:
    if stream is not None:
        stream.stop()


def get_system_log_lines(
    stream: LogStream | None = None,
    pipeline_runner: PipelineRunner | None = None,
) -> list[str]:
    lines = get_system_logs()
    if stream is not None:
        lines.extend(stream.get_system_log_lines())
    if pipeline_runner is not None and pipeline_runner.is_running:
        lines.append(f"{get_datetime_iso()} | INFO | pipeline running")
    return lines[-500:]


def get_model_logs_fallback(
    active_filter: str,
    stream: LogStream | None = None,
) -> list[str]:
    """Fallback logs when no app-managed pipeline runner is available."""
    if stream is not None and stream.is_running:
        return stream.get_logs_filtered(active_filter)
    # placeholder
    ts = get_datetime_iso()
    base: list[str] = [
        f"{ts} | translation | Hello → Hola",
        f"{ts} | transcription | hello world",
        f"{ts} | correction | Hello, world",
        f"{ts} | info | synthesis chunk: 24KB",
    ]
    if active_filter == "all":
        return base
    if active_filter == "errors":
        return [line for line in base if "| error |" in line]
    return [line for line in base if f"| {active_filter} |" in line]
