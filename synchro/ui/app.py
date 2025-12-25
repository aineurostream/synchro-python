from __future__ import annotations

import os
import json
import time
import logging
import asyncio
from typing import Any, cast
from pathlib import Path
from threading import Thread, Event, RLock

from hydra import initialize_config_dir, compose
from omegaconf import DictConfig, OmegaConf

from synchro.logging import setup_logging, get_logs, history
from .widgets import DropDownSelect

try:
    # Textual imports (optional at dev time)
    from textual import work, on
    from textual.reactive import reactive
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Container, Horizontal, Vertical
    from textual.widget import Widget
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
REFRESH_RATE: float = 0.2
MICROPHONE_WARNING = "[bold]Внимание![/bold] Если звук из колонок попадёт в микрофон, это может привести к нестабильной работе системы перевода."
DEFAULT_LANGS = [
    ("Английский", "en"),
    ("Русский", "ru"),
    ("Японский", "jp"),
    ("Китайский", "ch"),
]
TTS_ENGINES = [
    ("XTTS", "xtts"),
    ("Piper", "piper"),
    ("Vosk", "vosk"),
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


def update_converter_properties(
    config, 
    url: str = "http://127.0.0.1:50080", 
    lang_from: str = "en", 
    lang_to: str = "ru",
) -> None:
    for node in config.nodes:
        if node.node_type == "converter_seamless":
            node.server_url = url
            node.lang_from = lang_from
            node.lang_to = lang_to
            print("Replace node", node.model_dump_json())


class SystemInfoPanel(Static):
    """Simple system info block (uptime, node states, audio status)."""

    def __init__(self, title: str = "", info_getter=None) -> None:
        super().__init__()
        self.title = title
        self._info_getter = info_getter

    def on_mount(self) -> None:  # noqa: D401
        self.border_title = self.title
        self.add_class("section")

        self.set_interval(1.0, self.refresh_info)
        self.refresh_info()

    def refresh_info(self) -> None:
        info = self._info_getter() if self._info_getter else providers.get_system_info()

        nodes = ", ".join(f"{n['name']}:{n['state']}" for n in info["nodes"])
        audio = "yes" if info.get("audio_active") else "no"
        settings = "\n".join([f"{k}: {v}" for k, v in info["settings"]])
        
        self.update(
            "\n".join([
                f"Активно: {info['uptime']} сек.",
                # f"Nodes: {nodes}",
                # f"Audio: {audio}",
                f"Обновлено: {info['uptime_iso']}",
                f"Настройки\n{settings}",
                f"Процесс: {info['worker']}",
            ]),
        )


class LogsColumn(Vertical):
    """Logs column with preset filter selector and list view."""

    active_filter: str = ""
    FILTER_OPTIONS = {
        "__all__": "Все",
        "transcription": "Транскрипция",
        "gate": "Гейт",
        "translation": "Перевод",
        "correction": "Коррекция",
        "subtitles": "Субтитры",
        "subtitles_accumulator": "Аккумулятор субтитров",
    }
    FILTERS = {
        ("Все", None),
        ("Транскрипция", "transcription"),
        ("Гейт", "gate"),
        ("Перевод", "translation"),
        ("Коррекция", "correction"),
        ("Субтитры", "subtitles"),
        ("Аккумулятор субтитров", "subtitles_accumulator"),
    }
    FILTER_KEYS = tuple(FILTER_OPTIONS.keys())

    def __init__(self, title: str, with_filters: bool = False, fetcher=None) -> None:
        super().__init__()
        self.title = title
        self.with_filters = with_filters
        self.list_view = Log()
        self.status = Label()
        self.filter_set: RadioSet | Select | None = None
        self._fetcher = fetcher
        self.count = 0

    def on_mount(self) -> None:
        self.border_title = self.title
        self.add_class("section")

    def compose(self) -> ComposeResult:  # noqa: D401
        if self.with_filters:
            yield self.status

            # self.filter_set = RadioSet(
            #     *[RadioButton(v, value=k) for k, v in self.FILTER_OPTIONS.items()],
            #     id="model-log-filters",
            # )
            # yield self.filter_set

            self.filter_set = yield DropDownSelect(
                options=self.FILTERS,
                allow_blank=False,
                prompt="Фильтр",
                value=None,
                id="model-log-filters",
            )
        yield self.list_view

    # @on(RadioSet.Changed)
    # def filter_changed(self, event: RadioSet.Changed) -> None:
    #     if event.radio_set.id == "model-log-filters":
    #         filter = str(object=self.FILTER_KEYS[event.radio_set.pressed_index])
    #         self.active_filter = filter if filter != "__all__" else ""
    #         # self.list_view.clear()
    #         self.list_view.clear()
    #         self.refresh_logs(False)

    @on(Select.Changed, selector="#model-log-filters")
    def on_filter_changed(self, event: Select.Changed):
        value = event.value
        self.active_filter = value if value != "__all__" else ""
        self.list_view.clear()
        self.refresh_logs(False)

    def refresh_logs(self, only_new: bool = True) -> None:
        # self.list_view.clear()
        
        # if self.with_filters:
        #     items = self._fetcher(self.active_filter) if self._fetcher else []
        # else:
        #     items = providers.get_system_logs()

        messages = [
            # f'{x["action"]}: {x["message"]}'
            x
            for x in history.get(self.active_filter, only_new)
        ]

        new_count = len(messages)
        self.count = (self.count if only_new else 0) + new_count
        
        msg = [
            f"Всего сообщений {history.total}",
            f"В фильтре: {self.count}",
            f"Получено при обновлении: {new_count}",
        ]
        self.status.update("; ".join(x for x in msg if x))
        self.list_view.write_lines(messages)


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
        tts_opts: list[tuple[str, str]] = TTS_ENGINES

        def get_select(prompt: str, options, value, default = Select.BLANK) -> Select:
            valid_values = {x for _, x in options}
            value = value if value in valid_values else default
            result = Select[int](options, value=value, prompt=prompt)
            return result

        container = Container()
        container.border_title = "Настройки"
        container.add_class("section")
        with container:
            with Vertical():
                # yield Label("Настройки", classes="title")
                self.select_input = get_select("Устройство ввода", in_opts, self.app.settings.input_device)
                self.select_output = get_select("Устройство вывода", out_opts, self.app.settings.output_device)
                self.select_lang_from = get_select("Основной язык спикера", DEFAULT_LANGS, self.app.settings.lang_from)
                self.select_lang_to = get_select("Язык перевода", DEFAULT_LANGS, self.app.settings.lang_to)
                self.select_tts = get_select("Движок озвучания", tts_opts, self.select_tts, "xtts")
                self.server_url = Input(placeholder="Сервер", value=self.app.settings.server_url)
                yield self.select_input
                yield Label(MICROPHONE_WARNING, variant="warning", expand=True)
                yield self.select_output
                yield self.select_lang_from
                yield self.select_lang_to
                yield self.select_tts
                yield self.server_url
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

    def __init__(self, *args, config: str, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.config = config

    def compose(self) -> ComposeResult:  # noqa: D401
        container = Container()
        container.border_title = "Конфиг"
        container.add_class("section")
        with container:
            with Vertical():
                yield TextArea.code_editor(
                    self.config, 
                    language="yml", 
                    theme="vscode_dark", 
                    soft_wrap=True, 
                    read_only=True,
                )
            with Horizontal():
                # yield Button("Применить", id="apply", variant="success")
                yield Button("OK", id="cancel")

    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.dismiss(None)


class Sidebar(Widget):
    def __init__(self, widget, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.widget = widget

    def compose(self) -> ComposeResult:
        with Vertical():
            yield self.widget


class SynchroTextualApp(App[Any]):
    TITLE = "Клиент - Нейрострим. Перевод"
    CSS_PATH = "app.tcss"

    BINDINGS = [
        Binding("`", "toggle_sidebar", "Логи", show=False),
        Binding("q", "quit", "Выход"),
        Binding("space", "toggle", "Старт/Стоп"),
        Binding("comma", "push_screen('settings_modal')", "Настройки"),
        Binding(".", "push_screen('config_modal')", "Конфиг"),
    ]

    show_sidebar = reactive(False)

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
        self._worker_stop_event: Event = Event()
        self._start_lock: RLock = RLock()
        self._worker_status: str | None = None
        self._manager = None
        self._active_threads: list[Thread] = []

        # App-level system log buffer and handler
        self._syslog_lines: list[str] = []
        self._syslog_handler: logging.Handler | None = None
        self.model_logs = LogsColumn("События", with_filters=True, fetcher=self._get_model_logs)
        self.system_logs = Log(auto_scroll=True)  # LogsColumn("Системные логи", with_filters=False, fetcher=self._get_system_logs)
        self.sys_info = SystemInfoPanel(title="Системная информация", info_getter=self._get_system_info)
        self.log_stream = None

        self.threads_empty = Label("Нет активных процессов", id="threads-empty")

    def compose(self) -> ComposeResult:  # noqa: D401
        yield Sidebar(self.system_logs)
        yield Header(show_clock=True)
        with Container():
            with Horizontal():
                with Vertical():
                    yield self.model_logs
                with Vertical():
                    yield self.sys_info
                    yield Container(id="threads-info")

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
        # self.theme = THEME
        self.model_logs.border_title = "События"
        self.model_logs.add_class("section")
        self.system_logs.border_title = "Логи"
        self.system_logs.add_class("section")

        self.install_screen(SettingsModal(classes="screen_modal"), name="settings_modal")
        self.install_screen(ConfigModal(config=self.config, classes="screen_modal"), name="config_modal")

    def on_ready(self):
        if not self.settings.is_complete():
            self.app.notify("Не сконфигурировано, открываю настройки", severity="warning")
            if not self.settings.is_complete():
                self.push_screen(
                    "settings_modal",
                    self._on_config_done,
                )

        self.logger.info("Call worker")
        self.run_worker(self.process(), exclusive=True)

    async def refresh_threads(self):
        info_container = self.query_one("#threads-info")

        if not self._manager or not self._manager._executing:
            # self._worker_status = "stopped"
            empty_widget = self.query_one("#threads-info")
            if not empty_widget:
                await info_container.mount(empty_widget)
        else:
            for widget in info_container.children:
                widget.remove()

            thread_list = self._manager._active_threads + [self._manager._exception_check_thread]
            for thread in thread_list:
                is_active = "Да" if (
                    getattr(thread, "_running", False)
                    or thread.is_alive()
                ) else "Нет"
                # is_active = f'{getattr(thread, "_running", None)} {thread.is_alive()}'
                # settings = json.dumps(
                #     getattr(thread, "_settings", {}),
                #     indent=4,
                #     ensure_ascii=False,
                #     default=str,
                # )
                settings = getattr(thread, "_settings", None)
                if settings:
                    settings = settings.model_dump_json(indent=4)
                incoming = json.dumps(getattr(thread, "_incoming", []), indent=4, default=str)
                outgoing = json.dumps(getattr(thread, "_outgoing", []), indent=4, default=str)
                
                node_data = {}
                node = getattr(thread, "node", None)
                if node:
                    func = getattr(node, "get_info", None)
                    if callable(func):
                        node_data = func()

                node_info = json.dumps(
                    node_data, 
                    indent=4,
                    ensure_ascii=False, 
                    default=str,
                )

                info = "\n\n".join([
                    # f"[b]{getattr(thread, "node", "")}[/b]",
                    f"Активно: {is_active}",
                    f"Настройки\n{settings}",
                    f"Входящие узлы\n{incoming}",
                    f"Исходящие узлы\n{outgoing}",
                    f"Данные\n{node_info}"
                ])
                widget = Static(f"{info}", markup=False)
                widget.border_title = thread.name
                widget.add_class("section")
                await info_container.mount(widget)

    # @work(thread=True, exclusive=True)
    async def process(self):
        self.logger.info("Listening events")
        # self.notify("Мониторинг событий активен")

        while True:
        
            if not self.settings.is_complete():
                self.notify("Конфигурация не завершена")
                self._worker_status = None
            elif self._worker_status == "start":
                self._worker_status = "starting"

                nodes, edges = GraphInitializer(
                    self.settings_client,
                    self.settings_pipeline,
                    self.settings_ai,
                    None,
                    self.working_dir,
                ).build()

                self._manager = GraphManager(
                    nodes, 
                    edges, 
                    self.settings_client, 
                    self.working_dir,
                )

                self._manager._foreground = False
                self._manager.execute()

                self._worker_status = "started"
                self.notify(message="Комната запущена")
            elif self._worker_status == "stop" and self._manager and self._manager._executing:
                self._worker_status == "stopping"

                self._manager.stop()
                self._manager = None

                self._worker_status == "stopped"
                self.notify(message="Комната остановлена")
            elif self._manager and self._manager._exception:
                self.notify(str(self._manager._exception), severity="error")
                self._manager = None
                self._worker_status = "error"

            await self.refresh_threads()
            self.system_logs.write_lines(get_logs())
            await asyncio.sleep(REFRESH_RATE)

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

    def _get_model_logs(self, active_filter: str) -> list[str]:
        if self.pipeline_runner is not None and self.pipeline_runner.is_running:
            return self.pipeline_runner.get_logs_filtered(active_filter)
        return providers.get_model_logs_fallback(active_filter, self.log_stream)

    def _get_system_info(self) -> dict[str, Any]:
        info = providers.get_system_info()
        info["worker"] = self._worker_status
        if self.pipeline_runner is not None and self.pipeline_runner.is_running:
            info["audio_active"] = True
        info["settings"] = self.app.settings
        return info

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

    def action_toggle(self) -> None:
        if not self._manager or not self._manager._executing:
            self._worker_status = "start"
        else:
            self._worker_status = "stop"

    def action_toggle_sidebar(self) -> None:
        """Toggle the sidebar visibility."""
        self.show_sidebar = not self.show_sidebar

    def watch_show_sidebar(self, show_sidebar: bool) -> None:
        """Set or unset visible class when reactive changes."""
        self.query_one(Sidebar).set_class(show_sidebar, "-visible")


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
    print("CLI arguments", args)

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
    print("UI settings and applied overrides", app_settings)

    fp = app_settings.config
    print("Load config from", fp.resolve())
    cfg = load_config_via_hydra(config_file=fp)
    text_config = OmegaConf.to_yaml(cfg, resolve=True)
    # print("Parsed config", text_config)
    core_config, settings, neural_config_dict = initialize_configs(cfg)

    update_converter_properties(
        config=core_config, 
        url=app_settings.server_url,
        lang_from=app_settings.lang_from,
        lang_to=app_settings.lang_to,
    )
    print("Updated with overrides core config")
    print(core_config.model_dump_json(indent=4))

    SynchroTextualApp(
        settings=app_settings,
        config=text_config,
        settings_pipeline=core_config,
        settings_client=settings,
        settings_ai=neural_config_dict,
    ).run()


if __name__ == "__main__":
    main()
