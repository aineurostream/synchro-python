import os
import logging

from datetime import datetime
from typing import Union


LOG_DIR = 'logs'
LOG_FORMAT = '%(asctime)s | %(filename)s: %(message)s'
DATE_FORMAT = '%d %B %Y | %H:%M:%S'

# create folder logs, if exists
os.makedirs(LOG_DIR, exist_ok=True)


def get_logger(name: str, log_file: str, level: int = logging.INFO) -> logging.Logger:
    """
    Creates and configures a logger with the given name, file to write to, and logging level.

    Args:
        name (str): The name of the logger.
        log_file (str): The name of the file to write logs to.
        level (int): The logging level (default is logging.INFO).

    Returns:
        logging.Logger: The configured logger.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    file_handler = logging.FileHandler(os.path.join(LOG_DIR, log_file))
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    return logger


app_logger = get_logger('app_logger', 'applogs.log')
err_logger = get_logger('err_logger', 'errlogs.log', logging.ERROR)
audio_logger = get_logger('audio_logger', 'audiolog.log')
context_logger = get_logger('context_logger', 'contextlog.log')


def log(message: str, log_type: Union[str, logging.Logger] = 'app') -> None:
    """
    Function for logging messages to the appropriate file.

    Args:
        message (str): The message to log.
        log_type (union[str, logging.Logger]): Log type ('app', 'err', 'audio', 'context') or logger instance.
    """
    if isinstance(log_type, str):
        log_type = log_type.lower()
        if log_type == 'app':
            app_logger.info(message)
        elif log_type == 'err':
            err_logger.error(message)
        elif log_type == 'audio':
            audio_logger.info(message)
        elif log_type == 'context':
            context_logger.info(message)
        else:
            app_logger.info(f"Неизвестный тип лога: {log_type}")
    elif isinstance(log_type, logging.Logger):
        log_type.info(message)
    else:
        raise TypeError("log_type должен быть строкой или экземпляром logging.Logger")
