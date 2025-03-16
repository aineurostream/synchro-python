import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from synchroagent.config import AppConfig
from synchroagent.database.models import (
    ClientRunSchema,
    ClientSchema,
    ConfigSchema,
    LogSchema,
    ReportSchema,
    RunStatus,
)
from synchroagent.main import app


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def mock_client_registry():
    with patch("synchroagent.api.deps.get_client_registry") as mock:
        mock_registry = MagicMock()
        mock.return_value = mock_registry
        yield mock_registry


@pytest.fixture()
def mock_config_registry():
    with patch("synchroagent.api.deps.get_config_registry") as mock:
        mock_registry = MagicMock()
        mock.return_value = mock_registry
        yield mock_registry


@pytest.fixture()
def mock_client_run_registry():
    with patch("synchroagent.api.deps.get_client_run_registry") as mock:
        mock_registry = MagicMock()
        mock.return_value = mock_registry
        yield mock_registry


@pytest.fixture()
def mock_log_registry():
    with patch("synchroagent.api.deps.get_log_registry") as mock:
        mock_registry = MagicMock()
        mock.return_value = mock_registry
        yield mock_registry


@pytest.fixture()
def mock_report_registry():
    with patch("synchroagent.api.deps.get_report_registry") as mock:
        mock_registry = MagicMock()
        mock.return_value = mock_registry
        yield mock_registry


@pytest.fixture()
def mock_client_process_manager():
    with patch("synchroagent.api.deps.get_client_process_manager") as mock:
        mock_manager = MagicMock()
        mock.return_value = mock_manager
        yield mock_manager


@pytest.fixture()
def mock_log_manager():
    with patch("synchroagent.api.deps.get_log_manager") as mock:
        mock_manager = MagicMock()
        mock.return_value = mock_manager
        yield mock_manager


@pytest.fixture()
def mock_report_manager():
    with patch("synchroagent.api.deps.get_report_manager") as mock:
        mock_manager = MagicMock()
        mock.return_value = mock_manager
        yield mock_manager


@pytest.fixture()
def sample_client():
    return ClientSchema(
        id=1,
        name="Test Client",
        description="Test client description",
        config_id=1,
    )


@pytest.fixture()
def sample_client_run():
    return ClientRunSchema(
        id=1,
        client_id=1,
        config_id=1,
        pid=12345,
        status=RunStatus.RUNNING,
        output_dir="/tmp/test_output",
        started_at="2023-01-01T00:00:00",
        finished_at=None,
        exit_code=None,
        report_id=None,
        log_id=None,
    )


@pytest.fixture()
def sample_log():
    return LogSchema(
        id=1,
        client_run_id=1,
        content="Test log content",
        log_type="stdout",
        created_at="2023-01-01T00:00:00",
    )


@pytest.fixture()
def sample_report():
    return ReportSchema(
        id=1,
        client_id=1,
        content="<html>Test report content</html>",
        size=30,
        generated_at="2023-01-01T00:00:00",
    )


@pytest.fixture()
def sample_config():
    return ConfigSchema(
        id=1,
        name="Test Config",
        content={"key": "value"},
        description="Test config description",
        created_at="2023-01-01T00:00:00",
        updated_at="2023-01-01T00:00:00",
    )


@pytest.fixture()
def temp_db_path():
    fd, path = tempfile.mkstemp()
    os.close(fd)
    yield path
    os.unlink(path)


@pytest.fixture()
def temp_outputs_dir():
    with tempfile.TemporaryDirectory() as tmpdirname:
        yield tmpdirname


@pytest.fixture()
def temp_reports_dir():
    with tempfile.TemporaryDirectory() as tmpdirname:
        yield tmpdirname


@pytest.fixture()
def test_app_config(temp_db_path, temp_outputs_dir, temp_reports_dir):
    return AppConfig(
        db_path=temp_db_path,
        log_level="DEBUG",
        outputs_dir=temp_outputs_dir,
        reports_dir=temp_reports_dir,
    )


@pytest.fixture()
def integration_client(test_app_config, monkeypatch):
    monkeypatch.setattr("synchroagent.api.deps.default_config", test_app_config)

    db_path = "synchroagent.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    from synchroagent.database import init_database as original_init_database

    db = original_init_database.__wrapped__()

    monkeypatch.setattr("synchroagent.database.init_database", lambda: db)
    monkeypatch.setattr("synchroagent.api.deps.init_database", lambda: db)

    with TestClient(app) as test_client:
        yield test_client
