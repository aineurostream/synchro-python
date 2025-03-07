import logging

from pythonjsonlogger.json import JsonFormatter


class CustomJsonFormatter(JsonFormatter):
    def __init__(self, *args: list, **kwargs: dict) -> None:  # type: ignore
        super().__init__(*args, **kwargs, json_ensure_ascii=False)


def setup_logging() -> None:
    formatter = CustomJsonFormatter()
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(handler)

    for h in root_logger.handlers[:]:
        if h is not handler:
            root_logger.removeHandler(h)
