import logging
from pythonjsonlogger.json import JsonFormatter


class CustomJsonFormatter(JsonFormatter):
    def __init__(self, *args, **kwargs):
        kwargs["json_ensure_ascii"] = False
        super().__init__(*args, **kwargs)


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
