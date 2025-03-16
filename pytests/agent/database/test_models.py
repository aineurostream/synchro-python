import pytest
from pydantic import ValidationError

from synchroagent.database.models import (
    ClientRunSchema,
    ClientSchema,
    ConfigSchema,
    LogSchema,
    LogType,
    ReportSchema,
    RunStatus,
)


def test_client_schema_validation():
    client = ClientSchema(id=1, name="test_client", config_id=1)
    assert client.id == 1
    assert client.name == "test_client"
    assert client.config_id == 1
    assert client.description is None
    client = ClientSchema(
        id=1,
        name="test_client",
        config_id=1,
        description="Test description",
    )
    assert client.description == "Test description"


def test_config_schema_validation():
    config = ConfigSchema(
        name="test_config",
        content={"key": "value"},
        created_at="2023-01-01T00:00:00Z",
        updated_at="2023-01-01T00:00:00Z",
    )
    assert config.name == "test_config"
    assert config.content == {"key": "value"}
    assert config.created_at == "2023-01-01T00:00:00Z"
    assert config.updated_at == "2023-01-01T00:00:00Z"
    assert config.description is None

    config = ConfigSchema(
        name="test_config",
        content={"key": "value"},
        description="Test description",
    )
    assert config.description == "Test description"
    with pytest.raises(ValidationError):
        ConfigSchema(content={"key": "value"})

    with pytest.raises(ValidationError):
        ConfigSchema(name="test_config")


def test_report_schema_validation():
    report = ReportSchema(
        client_id=1,
        content="<html>Test</html>",
        size=1000,
        generated_at="2023-01-01T00:00:00Z",
    )
    assert report.client_id == 1
    assert report.content == "<html>Test</html>"
    assert report.size == 1000
    assert report.generated_at == "2023-01-01T00:00:00Z"

    report = ReportSchema(client_id=1)
    assert report.client_id == 1
    assert report.content is None
    assert report.size is None
    assert report.generated_at is None

    with pytest.raises(ValidationError):
        ReportSchema()


def test_client_run_schema_validation():
    client_run = ClientRunSchema(
        client_id=1,
        config_id=1,
        pid=1000,
        status=RunStatus.RUNNING,
        output_dir="/tmp/output",
        report_id=1,
        log_id=1,
        exit_code=0,
        started_at="2023-01-01T00:00:00Z",
        finished_at="2023-01-01T01:00:00Z",
    )
    assert client_run.client_id == 1
    assert client_run.config_id == 1
    assert client_run.pid == 1000
    assert client_run.status == RunStatus.RUNNING
    assert client_run.output_dir == "/tmp/output"
    assert client_run.report_id == 1
    assert client_run.log_id == 1
    assert client_run.exit_code == 0
    assert client_run.started_at == "2023-01-01T00:00:00Z"
    assert client_run.finished_at == "2023-01-01T01:00:00Z"

    client_run = ClientRunSchema(client_id=1, config_id=1)
    assert client_run.client_id == 1
    assert client_run.config_id == 1
    assert client_run.pid is None
    assert client_run.status == RunStatus.CREATED
    assert client_run.output_dir is None
    assert client_run.report_id is None
    assert client_run.log_id is None
    assert client_run.exit_code is None
    assert client_run.started_at is None
    assert client_run.finished_at is None

    with pytest.raises(ValidationError):
        ClientRunSchema(client_id=1)

    with pytest.raises(ValidationError):
        ClientRunSchema(config_id=1)


def test_log_schema_validation():
    log = LogSchema(
        client_run_id=1,
        content="Test log content",
        log_type=LogType.STDOUT,
        created_at="2023-01-01T00:00:00Z",
    )
    assert log.client_run_id == 1
    assert log.content == "Test log content"
    assert log.log_type == LogType.STDOUT
    assert log.created_at == "2023-01-01T00:00:00Z"

    log = LogSchema(
        client_run_id=1,
        content="Test log content",
        log_type=LogType.STDERR,
    )
    assert log.client_run_id == 1
    assert log.content == "Test log content"
    assert log.log_type == LogType.STDERR
    assert log.created_at is None

    with pytest.raises(ValidationError):
        LogSchema(content="Test log content", log_type=LogType.STDOUT)

    with pytest.raises(ValidationError):
        LogSchema(client_run_id=1, log_type=LogType.STDOUT)

    with pytest.raises(ValidationError):
        LogSchema(client_run_id=1, content="Test log content")


def test_run_status_enum():
    assert RunStatus.CREATED == "created"
    assert RunStatus.RUNNING == "running"
    assert RunStatus.STOPPED == "stopped"
    assert RunStatus.FAILED == "failed"


def test_log_type_enum():
    assert LogType.STDOUT == "stdout"
    assert LogType.STDERR == "stderr"
    assert LogType.APPLICATION == "application"
