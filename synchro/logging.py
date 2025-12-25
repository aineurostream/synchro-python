import logging

from pythonjsonlogger.json import JsonFormatter


def get_logs():
    return []


def history():
    return dict()


class CustomJsonFormatter(JsonFormatter):
    def __init__(self, *args: list, **kwargs: dict) -> None:  # type: ignore
        super().__init__(*args, **kwargs, json_ensure_ascii=False)

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        # Добавляем имя потока
        log_record['threadName'] = record.threadName


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
