from unittest.mock import MagicMock

import pytest

from synchroagent.database.models import (
    ClientRunSchema,
    ClientSchema,
    ConfigSchema,
    LogSchema,
    LogType,
    ReportSchema,
    RunStatus,
)
from synchroagent.logic.client_process_manager import ClientProcessManager
from synchroagent.logic.log_manager import LogManager
from synchroagent.logic.report_manager import ReportManager


@pytest.fixture()
def mock_client_registry():
    return MagicMock()


@pytest.fixture()
def mock_client_run_registry():
    return MagicMock()


@pytest.fixture()
def mock_config_registry():
    return MagicMock()


@pytest.fixture()
def mock_log_registry():
    return MagicMock()


@pytest.fixture()
def mock_report_registry():
    return MagicMock()


@pytest.fixture()
def mock_log_manager():
    manager = MagicMock()
    manager.collect_logs.return_value = 123
    return manager


@pytest.fixture()
def mock_report_manager():
    manager = MagicMock()
    manager.generate_report.return_value = 456
    return manager


@pytest.fixture()
def client_process_manager(
    mock_client_registry,
    mock_client_run_registry,
    mock_config_registry,
    mock_log_manager,
    mock_report_manager,
):
    return ClientProcessManager(
        client_registry=mock_client_registry,
        client_run_registry=mock_client_run_registry,
        config_registry=mock_config_registry,
        log_manager=mock_log_manager,
        report_manager=mock_report_manager,
        outputs_dir="/tmp/test_outputs",
    )


@pytest.fixture()
def log_manager(mock_log_registry, mock_client_run_registry):
    return LogManager(
        log_registry=mock_log_registry,
        client_run_registry=mock_client_run_registry,
    )


@pytest.fixture()
def report_manager(
    mock_report_registry,
    mock_client_run_registry,
    mock_client_registry,
):
    return ReportManager(
        report_registry=mock_report_registry,
        client_run_registry=mock_client_run_registry,
        client_registry=mock_client_registry,
        reports_dir="/tmp/test_reports",
    )


@pytest.fixture()
def sample_client():
    return ClientSchema(
        id=1,
        name="test_client",
        config_id=1,
    )


@pytest.fixture()
def sample_config():
    return ConfigSchema(
        id=1,
        name="test_config",
        content={"key": "value"},
        description="Test config",
        created_at="2023-01-01T00:00:00",
        updated_at="2023-01-01T00:00:00",
    )


@pytest.fixture()
def sample_client_run():
    return ClientRunSchema(
        id=1,
        client_id=1,
        config_id=1,
        pid=12345,
        status=RunStatus.RUNNING,
        exit_code=None,
        output_dir="/tmp/test_outputs/run_1",
        report_id=None,
        log_id=None,
    )


@pytest.fixture()
def sample_client_run_stopped():
    return ClientRunSchema(
        id=1,
        client_id=1,
        config_id=1,
        pid=12345,
        status=RunStatus.STOPPED,
        exit_code=0,
        output_dir="/tmp/test_outputs/run_1",
        report_id=None,
        log_id=None,
    )


@pytest.fixture()
def sample_log():
    return LogSchema(
        id=1,
        client_run_id=1,
        content="Log content",
        log_type=LogType.APPLICATION,
        created_at="2023-01-01T01:30:00",
    )


@pytest.fixture()
def sample_report():
    return ReportSchema(
        id=1,
        client_id=1,
        content="<html>Test Report</html>",
        generated_at="2023-01-01T01:30:00",
        size=24,
    )
