import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def read_json_file(file_path: str) -> dict[str, Any] | None:
    if not Path(file_path).exists():
        logger.warning(f"File not found: {file_path}")
        return None

    try:
        with open(file_path) as f:
            data = json.load(f)
            if not isinstance(data, dict):
                logger.warning(f"JSON file {file_path} does not contain a dictionary")
                return None
            return data
    except Exception:
        logger.exception(f"Error reading JSON file {file_path}")
        return None


def get_current_datetime() -> datetime:
    return datetime.now(UTC)


def get_datetime_iso() -> str:
    return get_current_datetime().isoformat()


def ensure_dir_exists(dir_path: Path) -> None:
    dir_path.mkdir(parents=True, exist_ok=True)
