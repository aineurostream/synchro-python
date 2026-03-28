import logging
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def get_current_datetime() -> datetime:
    return datetime.now(UTC)


def get_datetime_iso() -> str:
    return get_current_datetime().isoformat()


def ensure_dir_exists(dir_path: Path) -> None:
    dir_path.mkdir(parents=True, exist_ok=True)
