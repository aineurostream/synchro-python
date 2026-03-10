import logging

from pythonjsonlogger.json import JsonFormatter

_MAX_LOG_LINES = 2000
_log_lines: list[str] = []


class CustomJsonFormatter(JsonFormatter):
    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs, json_ensure_ascii=False)


class InMemoryLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        message = self.format(record)
        _log_lines.append(message)
        if len(_log_lines) > _MAX_LOG_LINES:
            del _log_lines[: _MAX_LOG_LINES // 2]


def get_logs(_active_filter: str | None = None) -> list[str]:
    return list(_log_lines[-500:])


def setup_logging() -> logging.Logger:
    formatter = CustomJsonFormatter()
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    memory_handler = InMemoryLogHandler()
    memory_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    # Use DEBUG
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)
    root_logger.addHandler(memory_handler)

    for h in root_logger.handlers[:]:
        if h not in {handler, memory_handler}:
            root_logger.removeHandler(h)
    return root_logger
