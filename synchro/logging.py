import logging
import threading

from pythonjsonlogger.json import JsonFormatter

_MAX_LOG_LINES = 2000
_log_lines: list[str] = []
_log_lock = threading.Lock()
_setup_done = False


class CustomJsonFormatter(JsonFormatter):
    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs, json_ensure_ascii=False)


class InMemoryLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        message = self.format(record)
        with _log_lock:
            _log_lines.append(message)
            if len(_log_lines) > _MAX_LOG_LINES:
                del _log_lines[: _MAX_LOG_LINES // 2]


def get_logs(_active_filter: str | None = None) -> list[str]:
    with _log_lock:
        return list(_log_lines[-500:])


def setup_logging() -> logging.Logger:
    global _setup_done  # noqa: PLW0603
    if _setup_done:
        return logging.getLogger()

    formatter = CustomJsonFormatter()
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    memory_handler = InMemoryLogHandler()
    memory_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)
    root_logger.addHandler(memory_handler)

    _setup_done = True
    return root_logger
