from __future__ import annotations

from typing import cast
import os
import asyncio
from typing import Any
import logging
import time
from threading import Thread, Event, RLock
from pathlib import Path

from hydra import initialize_config_dir, compose
from omegaconf import DictConfig, OmegaConf

from synchro.logging import setup_logging, get_logs

try:
    # Textual imports (optional at dev time)
    from textual import on
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Container, Horizontal, Vertical
    from textual.reactive import reactive
    from textual.widgets import (
        Button,
        Footer,
        Header,
        Input,
        Label,
        ListItem,
        ListView,
        RadioButton,
        RadioSet,
        Select,
        Static,
        Log,
        TextArea,
    )
    try:
        from textual.screen import ModalScreen
    except Exception:
        from textual.screens import ModalScreen  # type: ignore[no-redef]
except Exception as _e:  # pragma: no cover - textual may be missing
    raise SystemExit(
        f"Textual import error: {type(_e).__name__}: {_e}. Install with `uv pip install textual`.",
    ) from _e

from . import providers
from .settings import UISettings, load_settings
from .providers import PipelineRunner

from synchro.config.schemas import (
    ProcessingGraphConfig,
    SeamlessConnectorNodeSchema,
)
from synchro.config.commons import NodeEventsCallback
from synchro.config.settings import SettingsSchema
from synchro.graph.graph_initializer import GraphInitializer
from synchro.graph.graph_manager import GraphManager

THEME: str = "solarized-light"
REFRESH_RATE: float = 1
MICROPHONE_WARNING = (
    "[bold]Внимание![/bold] "
    "Если звук из колонок попадёт в микрофон, "
    "это может привести к нестабильной работе системы перевода."
)
DEFAULT_LANGS = [
    ("Английский", "en"),
    ("Русский", "ru"),
    ("Японский", "jp"),
    ("Китайский", "ch"),
]

def file_resolver(path: str) -> bytes:
    with open(path, "rb") as fp:
        return fp.read()


OmegaConf.register_new_resolver("file", file_resolver)


def load_config_via_hydra(*, config_file: Path) -> DictConfig:
    """Load config using Hydra abstractions programmatically.

    Expects `config_file` to be a Hydra base config (e.g., config/config.yaml)
    and resolves groups (ai/pipeline/settings) via compose().
    """
    if not config_file.exists():
        raise FileNotFoundError(f"Config not found: {config_file}")

    config_dir = config_file.parent.resolve()
    config_name = config_file.stem
    with initialize_config_dir(version_base=None, config_dir=str(config_dir)):
        cfg = compose(config_name=config_name)

    return cast(DictConfig, cfg)


def initialize_configs(cfg: DictConfig) -> tuple[ProcessingGraphConfig, SettingsSchema, Any]:
    pipeline_config = cast(DictConfig, cfg["pipeline"])
    neural_config = cast(DictConfig, cfg["ai"])
    settings_config = cast(DictConfig, cfg["settings"])

    core_config = ProcessingGraphConfig.model_validate(pipeline_config)
    settings = SettingsSchema.model_validate(settings_config)
    neural_config_dict = OmegaConf.to_container(neural_config)

    return core_config, settings, neural_config_dict


def replace_server_url(config, url: str = "http://127.0.0.1:50080", lang_from: str = "en", lang_to: str = "ru") -> None:
    for node in config.nodes:
        if node.node_type == "converter_seamless":
            node.server_url = url
            node.lang_from = lang_from
            node.lang_to = lang_to
            print("Replace node", node.model_dump_json())


class SystemInfoPanel(Static):
    """Simple system info block (uptime, node states, audio status)."""

    def __init__(self, info_getter=None) -> None:
        super().__init__()
        self._info_getter = info_getter

    def on_mount(self) -> None:  # noqa: D401
        self.set_interval(1.0, self.refresh_info)
        self.refresh_info()

    def refresh_info(self) -> None:
        info = self._info_getter() if self._info_getter else providers.get_system_info()
        nodes = ", ".join(f"{n['name']}:{n['state']}" for n in info["nodes"])
        audio = "yes" if info.get("audio_active") else "no"
        self.update(
            "\n".join([
                f"Активно: {info['uptime']} сек.",
                # f"Nodes: {nodes}",
                # f"Audio: {audio}",
                f"Обновлено: {info['uptime_iso']}",
                f"Процесс: {info['worker'] and info['worker'].is_alive()}",
            ]),
        )


class LogsColumn(Vertical):
    """Logs column with preset filter selector and list view."""

    active_filter: reactive[str] = reactive("all")

    def __init__(self, title: str, with_filters: bool = False, fetcher=None) -> None:
        super().__init__()
        self.title = title
        self.with_filters = with_filters
        self.list_view = ListView()
        self.filter_set: RadioSet | None = None
        self._fetcher = fetcher

    def compose(self) -> ComposeResult:  # noqa: D401
        yield Label(self.title, classes="title")
        if self.with_filters:
            self.filter_set = RadioSet(
                *[RadioButton(lbl, value=lbl) for lbl in providers.get_preset_filters()],
                id="model-log-filters",
            )
            yield self.filter_set
        yield self.list_view

    @on(RadioSet.Changed)
    def filter_changed(self, event: RadioSet.Changed) -> None:
        if event.radio_set.id == "model-log-filters":
            self.active_filter = str(event.pressed.value)
            self.refresh_logs()

    def refresh_logs(self) -> None:
        self.list_view.clear()
        
        # if self.with_filters:
        #     items = self._fetcher(self.active_filter) if self._fetcher else []
        # else:
        #     items = providers.get_system_logs()
        log_lines = get_logs(self.active_filter)
        self.app.notify(log_lines)
        for line in log_lines:
            self.list_view.append(ListItem(Label(line)))


class SettingsModal(ModalScreen[dict[str, Any] | None]):
    """Configuration dialog shown on startup if no env config present.

    Returns selected config dict on Apply, or None on Cancel.
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Отмена"),
    ]

    def __init__(self, *args, defaults: dict[str, Any] | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._defaults = defaults or {}
        self.select_input: Select[int] | None = None
        self.select_lang_from: Select[str] | None = None
        self.select_lang_to: Select[str] | None = None
        self.select_output: Select[int] | None = None
        self.select_tts: Select[str] | None = None
        self.error_label = Label("")

    def compose(self) -> ComposeResult:  # noqa: D401
        in_devs = providers.list_input_devices()
        out_devs = providers.list_output_devices()
        in_opts: list[tuple[str, int]] = [
            (f"{d.device_id} — {d.name}", d.device_id) 
            for d in in_devs
        ] or [("0 — Default", 0)]
        out_opts: list[tuple[str, int]] = [
            (f"{d.device_id} — {d.name}", d.device_id) 
            for d in out_devs
        ] or [("1 — Default", 1)]
        tts_opts: list[tuple[str, str]] = [
            ("xtts", "xtts"),
            ("piper", "piper"),
            ("vosk", "vosk"),
        ]

        def get_select(prompt: str, options, value, default = Select.BLANK) -> Select:
            valid_values = {x for _, x in options}
            value = value if value in valid_values else default
            result = Select[int](options, value=value, prompt=prompt)
            return result

        with Container():
            with Vertical():
                yield Label("Настройки", classes="title")
                self.select_input = get_select("Устройство ввода", in_opts, self.app.settings.input_device)
                self.select_output = get_select("Устройство вывода", out_opts, self.app.settings.output_device)
                self.select_lang_from = get_select("Основной язык спикера", DEFAULT_LANGS, self.select_lang_from)
                self.select_lang_to = get_select("Язык перевода", DEFAULT_LANGS, self.select_lang_to)
                self.select_tts = get_select("Движок озвучания", tts_opts, self.select_tts, "xtts")
                yield self.select_input
                yield Label(MICROPHONE_WARNING, variant="warning", expand=True)
                yield self.select_output
                yield self.select_lang_from
                yield self.select_lang_to
                yield self.select_tts
                yield self.error_label
            with Horizontal():
                yield Button("Применить", id="apply", variant="success")
                yield Button("Отмена", id="cancel", variant="error")

        # Apply defaults if provided
        try:
            if self._defaults.get("input_device") is not None and self.select_input:
                self.select_input.value = int(self._defaults["input_device"])  # type: ignore[assignment]
            if self._defaults.get("output_device") is not None and self.select_output:
                self.select_output.value = int(self._defaults["output_device"])  # type: ignore[assignment]
            if self._defaults.get("lang_from") and self.select_lang_from:
                self.select_lang_from.value = str(self._defaults["lang_from"])  # type: ignore[assignment]
            if self._defaults.get("lang_to") and self.select_lang_to:
                self.select_lang_to.value = str(self._defaults["lang_to"])  # type: ignore[assignment]
            if self._defaults.get("tts_engine") and self.select_tts:
                self.select_tts.value = str(self._defaults["tts_engine"])  # type: ignore[assignment]
        except Exception:
            pass

    @on(Button.Pressed, "#apply")
    def on_apply(self) -> None:
        if not (self.select_input and self.select_output and self.select_lang_from and self.select_lang_to and self.select_tts):
            return
        dev = self.select_input.value
        out_dev = self.select_output.value
        src = self.select_lang_from.value
        dst = self.select_lang_to.value
        tts = self.select_tts.value
        if dev is None or out_dev is None or src is None or dst is None or tts is None:
            self.error_label.update("Please fill all fields")
            return
        self.dismiss({
            "input_device": dev,
            "output_device": out_dev,
            "lang_from": str(src),
            "lang_to": str(dst),
            "tts_engine": str(tts),
        })

    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.dismiss(None)


class ConfigModal(ModalScreen[dict[str, Any] | None]):

    BINDINGS = [
        Binding("escape", "dismiss", "Отмена"),
    ]

    def __init__(self, *args, config: str = "", defaults: dict[str, Any] | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.config = config
        self._defaults = defaults or {}
        self.select_input: Select[int] | None = None
        self.select_lang_from: Select[str] | None = None
        self.select_lang_to: Select[str] | None = None
        self.select_output: Select[int] | None = None
        self.select_tts: Select[str] | None = None
        self.error_label = Label("")

    def compose(self) -> ComposeResult:  # noqa: D401
        with Container():
            yield Label("Конфиг", classes="title")
            with Vertical():
                yield TextArea.code_editor(self.config, language="yml", theme="vscode_dark", soft_wrap=True, read_only=True)
            with Horizontal():
                # yield Button("Применить", id="apply", variant="success")
                yield Button("OK", id="cancel")

        # Apply defaults if provided
        try:
            if self._defaults.get("input_device") is not None and self.select_input:
                self.select_input.value = int(self._defaults["input_device"])  # type: ignore[assignment]
            if self._defaults.get("output_device") is not None and self.select_output:
                self.select_output.value = int(self._defaults["output_device"])  # type: ignore[assignment]
            if self._defaults.get("lang_from") and self.select_lang_from:
                self.select_lang_from.value = str(self._defaults["lang_from"])  # type: ignore[assignment]
            if self._defaults.get("lang_to") and self.select_lang_to:
                self.select_lang_to.value = str(self._defaults["lang_to"])  # type: ignore[assignment]
            if self._defaults.get("tts_engine") and self.select_tts:
                self.select_tts.value = str(self._defaults["tts_engine"])  # type: ignore[assignment]
        except Exception:
            pass

    @on(Button.Pressed, "#apply")
    def on_apply(self) -> None:
        if not (self.select_input and self.select_output and self.select_lang_from and self.select_lang_to and self.select_tts):
            return
        dev = self.select_input.value
        out_dev = self.select_output.value
        src = self.select_lang_from.value
        dst = self.select_lang_to.value
        tts = self.select_tts.value
        if dev is None or out_dev is None or src is None or dst is None or tts is None:
            self.error_label.update("Please fill all fields")
            return
        self.dismiss({
            "input_device": dev,
            "output_device": out_dev,
            "lang_from": str(src),
            "lang_to": str(dst),
            "tts_engine": str(tts),
        })

    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.dismiss(None)


class SynchroTextualApp(App[Any]):
    TITLE = "Клиент - Нейрострим. Перевод"
    CSS_PATH = "app.tcss"

    BINDINGS = [
        Binding("r", "refresh", "Refresh", show=False),
        Binding("q", "quit", "Quit"),
        Binding("s", "push_screen('settings_modal')", "Настройки"),
        Binding("c", "push_screen('config_modal')", "Конфиг"),
    ]

    def __init__(
            self, 
            settings: UISettings | None = None,
            config: str = "",
            settings_pipeline = None,
            settings_client = None,
            settings_ai = None,
        ) -> None:
        super().__init__()
        self.config = config
        self.settings_pipeline = settings_pipeline
        self.settings_client = settings_client
        self.settings_ai = settings_ai
        self.working_dir = None

        self.logger = setup_logging()
        self.settings = settings or load_settings()
        self.pipeline_runner: PipelineRunner | None = None
        self._ticker_started: bool = False
        self._worker_thread: Thread | None = None
        self._worker_stop: Event = Event()
        self._start_lock: RLock = RLock()
        # App-level system log buffer and handler
        self._syslog_lines: list[str] = []
        self._syslog_handler: logging.Handler | None = None
        self.model_logs = LogsColumn("События", with_filters=True, fetcher=self._get_model_logs)
        self.system_logs = Log(auto_scroll=True) #LogsColumn("Системные логи", with_filters=False, fetcher=self._get_system_logs)
        self.sys_info = SystemInfoPanel(info_getter=self._get_system_info)
        self.log_stream = None

    def compose(self) -> ComposeResult:  # noqa: D401
        yield Header(show_clock=True)
        with Horizontal():
            with Vertical():
                yield self.model_logs
            with Vertical():
                yield self.system_logs

                yield Label("Системная информация")
                yield self.sys_info
        yield Footer()

    def on_mount(self) -> None:  # noqa: D401
        """
        Set up callbacks after the app is mounted.
        
        Initializes:
        1. TUI callback for updating the interface
        2. File logging callback for event tracking
        
        
        Timing:
        - on_mount is called after all widgets are created and mounted
        - It's safe to query and reference widgets here
        - Perfect place for post-initialization setup
        
        Widget Access:
        - query_one("#message-container") works here because widgets exist
        - Would fail if called in __init__ (widgets don't exist yet)
        
        Lifecycle Order:
        - Textual App Lifecycle
            1. __init__()           # Initial setup
            2. compose()           # Create widgets
            3. on_mount()         # Post-mount setup
            4. on_ready()        # App ready for user interaction
        
        Best Practices:
        - Use __init__ for basic initialization
        - Use compose for widget creation
        - Use on_mount for:
            - Widget queries
            - Event handlers setup
            - Callback registration
            - Post-initialization configuration
        
        This method is crucial for proper initialization timing in Textual applications, ensuring all components are properly set up after the UI is ready.
        """
        self.install_screen(SettingsModal(classes="screen_modal"), name="settings_modal")
        self.install_screen(ConfigModal(config=self.config, classes="screen_modal"), name="config_modal")

        # Attach root handler that writes to in-memory buffer and worker.log
        # self._attach_system_log_handler()
        # Show any early logs immediately
        # self.system_logs.write_lines(get_logs())
            
        # Start background worker that will start client when configured
        # self._start_worker()

        # Do not start periodic refresh until config is confirmed

    def on_ready(self):
        if not self.settings.is_complete():
            self.app.notify("Не сконфигурировано — открою настройки")
            # Run directly in UI thread; no need for call_from_thread here
            self._maybe_show_config()
        else:
            self.logger.info("Call worker")
            self.run_worker(self.process(), exclusive=True)

    async def process(self):
        try:
            self.logger.info("Get started")
            counter = 0

            nodes, edges = GraphInitializer(
                self.settings_client,
                self.settings_pipeline,
                self.settings_ai,
                None,
                self.working_dir,
            ).build()
            full_graph = GraphManager(
                nodes, 
                edges, 
                self.settings_client, 
                self.working_dir,
            )
            full_graph.execute()

            while True:
                self.logger.info(f"Work... %s", counter)
                self.system_logs.write_lines(get_logs())
                counter += 1
                await asyncio.sleep(REFRESH_RATE)

            self.logger.info("Worker shutdown")
        except Exception as exc:
            self.logger.info(f"Worker error: %s", exc)
            self.system_logs.write_lines(get_logs())

    def _maybe_show_config(self) -> None:
        # Always confirm configuration via modal, then start pipeline
        if not self.settings.is_complete():
            self.push_screen(
                "settings_modal",
                self._on_config_done,
            )

    def _on_config_done(self, result: dict[str, Any] | None) -> None:
        if not result:
            return
        
        # Persist to settings and environment for downstream tools
        self.settings.input_device = int(result["input_device"])  # type: ignore[assignment]
        self.settings.lang_from = str(result["lang_from"])  # type: ignore[assignment]
        self.settings.lang_to = str(result["lang_to"])  # type: ignore[assignment]
        if "output_device" in result:
            self.settings.output_device = int(result["output_device"])  # type: ignore[assignment]
        if "tts_engine" in result:
            self.settings.tts_engine = str(result["tts_engine"])  # type: ignore[assignment]
        os.environ["INPUT_DEVICE"] = str(self.settings.input_device)
        os.environ["OUTPUT_DEVICE"] = str(self.settings.output_device or "")
        os.environ["LANG_FROM"] = str(self.settings.lang_from)
        os.environ["LANG_TO"] = str(self.settings.lang_to)
        os.environ["TTS_ENGINE"] = str(self.settings.tts_engine or "")
        
        self._ensure_pipeline_started()
        # Now start periodic refresh and do an initial tick
        self.refresh_tick()
        if not self._ticker_started:
            self.set_interval(1.5, self.refresh_tick)
            self._ticker_started = True

    def _ensure_pipeline_started(self) -> None:
        with self._start_lock:
            if self.pipeline_runner is None:
                self.pipeline_runner = PipelineRunner(self.settings)
            if not self.pipeline_runner.is_running:
                self.pipeline_runner.start()

    def _get_model_logs(self, active_filter: str) -> list[str]:
        if self.pipeline_runner is not None and self.pipeline_runner.is_running:
            return self.pipeline_runner.get_logs_filtered(active_filter)
        return providers.get_model_logs_fallback(active_filter, self.log_stream)

    def _get_system_info(self) -> dict[str, Any]:
        info = providers.get_system_info()
        info["worker"] = self._worker_thread
        if self.pipeline_runner is not None and self.pipeline_runner.is_running:
            info["audio_active"] = True
        return info

    def _settings_defaults(self) -> dict[str, Any]:
        return {
            "input_device": self.settings.input_device,
            "output_device": self.settings.output_device,
            "lang_from": self.settings.lang_from,
            "lang_to": self.settings.lang_to,
            "tts_engine": self.settings.tts_engine,
        }

    def refresh_tick(self) -> None:
        # Only refresh lists; do not start any background connections here
        self.app.notify(str(get_logs()))
        self.model_logs.write_line("Test")
        self.system_logs.write_lines(get_logs())

    def _get_system_logs(self, _unused: Any = None) -> list[str]:
        # Combine app-level root logs with providers' logs
        combined: list[str] = []
        combined.extend(self._syslog_lines[-500:])
        combined.extend(providers.get_system_log_lines(self.log_stream, self.pipeline_runner))
        # Keep order and drop duplicates
        seen: set[str] = set()
        result: list[str] = []
        for line in combined[-500:]:
            if line in seen:
                continue
            seen.add(line)
            result.append(line)
        return result[-500:]

    # --- Background worker ---
    def _start_worker(self) -> None:
        if self._worker_thread and self._worker_thread.is_alive():
            return

        def _loop() -> None:
            counter = 0
            self.logger.info("Get started")
            while not self._worker_stop.is_set():
                # try:
                #     if self.settings.is_complete():
                #         # Start pipeline if not running yet
                #         if self.pipeline_runner is None or not self.pipeline_runner.is_running:
                #             self._ensure_pipeline_started()
                            
                #     time.sleep(0.5)
                # except Exception:
                #     time.sleep(0.5)
                try:
                    self.logger.info("Work loop...")
                    self.app.notify(f"Worker... {counter}")
                    if counter == 10: 1/0
                except Exception as exc:
                    self.logger.info("Oops! %s", exc)
                    self.app.notify(f"Error: {exc}")
                    return
                
                time.sleep(1)
                counter += 1
                self.system_logs.write_lines(get_logs())

        self._worker_stop.clear()
        self._worker_thread = Thread(target=_loop, name="UIWorker", daemon=True)
        self._worker_thread.start()

    def on_shutdown(self) -> None:  # type: ignore[override]
        # Stop background worker
        self._worker_stop.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=1.0)
        self._worker_thread = None
        # Detach system log handler
        if hasattr(self, "_syslog_handler") and self._syslog_handler is not None:
            try:
                logging.getLogger().removeHandler(self._syslog_handler)
            except Exception:
                pass
            self._syslog_handler = None
    
    def _attach_system_log_handler(self) -> None:
        if hasattr(self, "_syslog_handler") and self._syslog_handler is not None:
            return
        class _UIBufferedFileHandler(logging.Handler):
            def __init__(self, sink: list[str], file_path: str) -> None:
                super().__init__()
                self._sink = sink
                self._file_path = file_path
                fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
                self.setFormatter(fmt)
                self.setLevel(logging.INFO)
            def emit(self, record: logging.LogRecord) -> None:  # noqa: D401
                try:
                    msg = self.format(record)
                    self._sink.append(msg)
                    if len(self._sink) > 2000:
                        del self._sink[:1000]
                    with open(self._file_path, "a", encoding="utf-8") as f:
                        f.write(msg + "\n")
                except Exception:
                    pass
        handler = _UIBufferedFileHandler(self._syslog_lines, "worker.log")
        self._syslog_handler = handler
        root = logging.getLogger()
        root.addHandler(handler)
        if root.level > logging.INFO:
            root.setLevel(logging.INFO)

    def action_refresh(self) -> None:
        self.refresh_tick()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Synchro Textual UI")
    parser.add_argument("--input-device", type=int, default=None)
    parser.add_argument("--output-device", type=int, default=None)
    parser.add_argument("--lang-from", type=str, default=None)
    parser.add_argument("--lang-to", type=str, default=None)
    parser.add_argument("--tts-engine", type=str, default=None)
    parser.add_argument(
        "--server_url",
        type=str,
        default=None,
        help="Socket server URL (e.g., http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config/mic.yaml",
        help="Hydra base config name (default: config)",
    )

    args = parser.parse_args()
    overrides = {
        "input_device": args.input_device,
        "output_device": args.output_device,
        "lang_from": args.lang_from,
        "lang_to": args.lang_to,
        "tts_engine": args.tts_engine,
        "server_url": args.server_url,
        "config": args.config,
    }

    app_settings = load_settings(overrides)
    print(app_settings)
    fp = app_settings.config.resolve()
    print(fp)
    cfg = load_config_via_hydra(config_file=fp)
    config = OmegaConf.to_yaml(cfg, resolve=True)
    print(config)
    core_config, settings, neural_config_dict = initialize_configs(cfg)
    replace_server_url(config=core_config)

    print(core_config)

    nodes, edges = GraphInitializer(
        settings,
        core_config,
        neural_config_dict,
        None,
        None,
    ).build()
    full_graph = GraphManager(
        nodes, 
        edges, 
        settings, 
        None,
    )
    full_graph.execute()

    SynchroTextualApp(
        settings=app_settings,
        config=config,
        settings_pipeline=core_config,
        settings_client=settings,
        settings_ai=neural_config_dict,
    ).run()


if __name__ == "__main__":
    main()
