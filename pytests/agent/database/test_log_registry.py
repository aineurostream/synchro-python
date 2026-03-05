from synchroagent.database.client_run_registry import ClientRunCreate
from synchroagent.database.log_registry import (
    LogCreate,
    LogType,
    LogUpdate,
)
from synchroagent.database.models import RunStatus


def test_log_create(log_registry, test_client_run_item):
    log_create = LogCreate(
        client_run_id=test_client_run_item.id,
        content="Test log content",
        log_type=LogType.STDOUT,
    )
    log = log_registry.create(log_create)

    assert log.id is not None
    assert log.client_run_id == test_client_run_item.id
    assert log.content == "Test log content"
    assert log.log_type == LogType.STDOUT
    assert log.created_at is not None


def test_log_update(log_registry, test_client_run_item):
    log_create = LogCreate(
        client_run_id=test_client_run_item.id,
        content="Original content",
        log_type=LogType.STDERR,
    )
    log = log_registry.create(log_create)

    log_update = LogUpdate(
        content="Updated content",
        log_type=LogType.APPLICATION,
    )
    updated_log = log_registry.update(log.id, log_update)

    assert updated_log is not None
    assert updated_log.id == log.id
    assert updated_log.client_run_id == test_client_run_item.id
    assert updated_log.content == "Updated content"
    assert updated_log.log_type == LogType.APPLICATION


def test_log_get_by_id(log_registry, test_client_run_item):
    log_create = LogCreate(
        client_run_id=test_client_run_item.id,
        content="Get by ID test",
        log_type=LogType.STDOUT,
    )
    created_log = log_registry.create(log_create)

    log = log_registry.get_by_id(created_log.id)

    assert log is not None
    assert log.id == created_log.id
    assert log.client_run_id == test_client_run_item.id
    assert log.content == "Get by ID test"
    assert log.log_type == LogType.STDOUT


def test_log_delete(log_registry, test_client_run_item):
    log_create = LogCreate(
        client_run_id=test_client_run_item.id,
        content="Delete test",
        log_type=LogType.STDOUT,
    )
    created_log = log_registry.create(log_create)

    assert log_registry.exists(created_log.id)

    result = log_registry.delete(created_log.id)

    assert result is True
    assert not log_registry.exists(created_log.id)
    assert log_registry.get_by_id(created_log.id) is None


def test_log_get_logs_by_client_run(log_registry, test_client_run_item):
    log_registry.create(
        LogCreate(
            client_run_id=test_client_run_item.id,
            content="Log 1",
            log_type=LogType.STDOUT,
        ),
    )
    log_registry.create(
        LogCreate(
            client_run_id=test_client_run_item.id,
            content="Log 2",
            log_type=LogType.STDERR,
        ),
    )
    log_registry.create(
        LogCreate(
            client_run_id=test_client_run_item.id,
            content="Log 3",
            log_type=LogType.APPLICATION,
        ),
    )

    logs = log_registry.get_logs_by_client_run(test_client_run_item.id)

    assert len(logs) == 3
    log_contents = [log.content for log in logs]
    assert "Log 1" in log_contents
    assert "Log 2" in log_contents
    assert "Log 3" in log_contents

    log_types = [log.log_type for log in logs]
    assert LogType.STDOUT in log_types
    assert LogType.STDERR in log_types
    assert LogType.APPLICATION in log_types


def test_log_filter(
    log_registry,
    client_run_registry,
    test_client_item,
    test_config_item,
):
    run1 = client_run_registry.create(
        ClientRunCreate(
            client_id=test_client_item.id,
            config_id=test_config_item.id,
            status=RunStatus.CREATED,
        ),
    )
    run2 = client_run_registry.create(
        ClientRunCreate(
            client_id=test_client_item.id,
            config_id=test_config_item.id,
            status=RunStatus.CREATED,
        ),
    )

    log_registry.create(
        LogCreate(client_run_id=run1.id, content="Run 1 Log", log_type=LogType.STDOUT),
    )
    log_registry.create(
        LogCreate(client_run_id=run2.id, content="Run 2 Log", log_type=LogType.STDOUT),
    )

    run1_logs = log_registry.filter(client_run_id=run1.id)
    run2_logs = log_registry.filter(client_run_id=run2.id)

    assert len(run1_logs) == 1
    assert run1_logs[0].content == "Run 1 Log"

    assert len(run2_logs) == 1
    assert run2_logs[0].content == "Run 2 Log"
