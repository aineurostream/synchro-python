import pytest

from synchroagent.config import AppConfig


@pytest.fixture()
def test_app_config() -> AppConfig:
    """Fixture for test application configuration."""
    return AppConfig(
        db_path=":memory:",
        log_level="DEBUG",
        outputs_dir="/tmp/test_outputs",
        reports_dir="/tmp/test_reports",
    )
