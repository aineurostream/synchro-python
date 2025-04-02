import signal
from unittest.mock import MagicMock, patch

import pytest

from synchroagent.database.models import RunStatus
from synchroagent.logic.client_process_manager import ClientProcessManager


def test_validate_client_and_config_success(
    client_process_manager,
    mock_client_registry,
    mock_config_registry,
    sample_client,
    sample_config,
):
    mock_client_registry.get_by_id.return_value = sample_client
    mock_config_registry.get_by_id.return_value = sample_config

    client, config = client_process_manager._validate_client_and_config(1, 1)

    assert client == sample_client
    assert config == sample_config
    mock_client_registry.get_by_id.assert_called_once_with(1)
    mock_config_registry.get_by_id.assert_called_once_with(1)


def test_validate_client_and_config_client_not_found(
    client_process_manager,
    mock_client_registry,
    mock_config_registry,
):
    mock_client_registry.get_by_id.return_value = None

    with pytest.raises(ValueError, match="Client not found: 1"):
        client_process_manager._validate_client_and_config(1, 1)


def test_validate_client_and_config_config_not_found(
    client_process_manager,
    mock_client_registry,
    mock_config_registry,
    sample_client,
):
    mock_client_registry.get_by_id.return_value = sample_client
    mock_config_registry.get_by_id.return_value = None

    with pytest.raises(ValueError, match="Configuration not found: 1"):
        client_process_manager._validate_client_and_config(1, 1)


def test_create_client_run_success(
    client_process_manager,
    mock_client_run_registry,
):
    mock_client_run_registry.create.return_value = 1

    client_run_id = client_process_manager._create_client_run(1, 1)

    assert client_run_id == 1
    mock_client_run_registry.create.assert_called_once()


def test_create_client_run_failure(
    client_process_manager,
    mock_client_run_registry,
):
    mock_client_run_registry.create.return_value = None

    with pytest.raises(RuntimeError, match="Failed to create client run record"):
        client_process_manager._create_client_run(1, 1)


@patch("synchroagent.logic.client_process_manager.subprocess.Popen")
@patch("synchroagent.logic.client_process_manager.Path.is_file")
def test_start_process_success(
    mock_is_file,
    mock_popen,
    client_process_manager,
    mock_client_run_registry,
    sample_config,
    sample_client_run,
):
    mock_is_file.return_value = True
    mock_process = MagicMock()
    mock_process.pid = 12345
    mock_popen.return_value = mock_process
    mock_client_run_registry.get_by_id.return_value = sample_client_run

    result = client_process_manager._start_process(sample_config, 1)

    assert result == sample_client_run
    mock_popen.assert_called_once()
    mock_client_run_registry.update.assert_called_once()


@patch("synchroagent.logic.client_process_manager.Path.is_file")
def test_start_process_hydra_script_not_found(
    mock_is_file,
    client_process_manager,
    sample_config,
):
    mock_is_file.return_value = False

    with pytest.raises(FileNotFoundError):
        client_process_manager._start_process(sample_config, 1)


@patch("synchroagent.logic.client_process_manager.subprocess.Popen")
@patch("synchroagent.logic.client_process_manager.Path.is_file")
def test_start_process_exception(
    mock_is_file,
    mock_popen,
    client_process_manager,
    mock_client_run_registry,
    sample_config,
):
    mock_is_file.return_value = True
    mock_popen.side_effect = Exception("Test error")

    with pytest.raises(RuntimeError, match="Failed to start client process"):
        client_process_manager._start_process(sample_config, 1)

    mock_client_run_registry.update_status.assert_called_once_with(
        1,
        RunStatus.FAILED,
    )


@patch.object(ClientProcessManager, "_validate_client_and_config")
@patch.object(ClientProcessManager, "_create_client_run")
@patch.object(ClientProcessManager, "_start_process")
def test_start_client_success(
    mock_start_process,
    mock_create_client_run,
    mock_validate,
    client_process_manager,
    sample_client,
    sample_config,
    sample_client_run,
):
    mock_validate.return_value = (sample_client, sample_config)
    mock_create_client_run.return_value = 1
    mock_start_process.return_value = sample_client_run

    result = client_process_manager.start_client(1, 1)

    assert result == sample_client_run
    mock_validate.assert_called_once_with(1, 1)
    mock_create_client_run.assert_called_once_with(1, 1)
    mock_start_process.assert_called_once_with(sample_config, 1)


@patch.object(ClientProcessManager, "_validate_client_and_config")
def test_start_client_exception(
    mock_validate,
    client_process_manager,
):
    mock_validate.side_effect = ValueError("Test error")

    with pytest.raises(ValueError, match="Test error"):
        client_process_manager.start_client(1, 1)


@patch("synchroagent.logic.client_process_manager.os.killpg")
@patch("synchroagent.logic.client_process_manager.os.getpgid")
def test_stop_client_run_success(
    mock_getpgid,
    mock_killpg,
    client_process_manager,
    mock_client_run_registry,
    sample_client_run,
):
    mock_client_run_registry.get_by_id.return_value = sample_client_run
    mock_getpgid.return_value = sample_client_run.pid
    mock_client_run_registry.get_by_id.return_value = sample_client_run

    result = client_process_manager.stop_client_run(1)

    assert result == sample_client_run
    mock_killpg.assert_called_once_with(sample_client_run.pid, signal.SIGTERM)
    mock_client_run_registry.update_run_status.assert_called_once()


def test_stop_client_run_not_found(
    client_process_manager,
    mock_client_run_registry,
):
    mock_client_run_registry.get_by_id.return_value = None

    with pytest.raises(ValueError, match="Client run not found: 1"):
        client_process_manager.stop_client_run(1)


def test_stop_client_run_not_running(
    client_process_manager,
    mock_client_run_registry,
    sample_client_run_stopped,
):
    mock_client_run_registry.get_by_id.return_value = sample_client_run_stopped

    with pytest.raises(ValueError, match="Client run is not running: 1"):
        client_process_manager.stop_client_run(1)


def test_stop_client_run_no_pid(
    client_process_manager,
    mock_client_run_registry,
    sample_client_run,
):
    no_pid_run = sample_client_run.copy(update={"pid": None})
    mock_client_run_registry.get_by_id.return_value = no_pid_run

    with pytest.raises(ValueError, match="Client run has no process ID: 1"):
        client_process_manager.stop_client_run(1)


@patch("synchroagent.logic.client_process_manager.os.killpg")
@patch("synchroagent.logic.client_process_manager.os.getpgid")
def test_stop_client_run_process_not_found(
    mock_getpgid,
    mock_killpg,
    client_process_manager,
    mock_client_run_registry,
    sample_client_run,
):
    mock_client_run_registry.get_by_id.return_value = sample_client_run
    mock_getpgid.return_value = sample_client_run.pid
    mock_killpg.side_effect = ProcessLookupError("No such process")
    mock_client_run_registry.get_by_id.return_value = sample_client_run

    result = client_process_manager.stop_client_run(1)

    assert result == sample_client_run
    mock_client_run_registry.update_run_status.assert_called_once()


def test_get_active_runs(
    client_process_manager,
    mock_client_run_registry,
    sample_client_run,
):
    mock_client_run_registry.get_active_runs.return_value = [sample_client_run]

    result = client_process_manager.get_active_runs()

    assert result == [sample_client_run]
    mock_client_run_registry.get_active_runs.assert_called_once()


def test_get_client_runs(
    client_process_manager,
    mock_client_run_registry,
    sample_client_run,
):
    mock_client_run_registry.get_runs_by_client_id.return_value = [
        sample_client_run,
    ]

    result = client_process_manager.get_client_runs(1)

    assert result == [sample_client_run]
    mock_client_run_registry.get_runs_by_client_id.assert_called_once_with(1, 10)


@patch("synchroagent.logic.client_process_manager.os.kill")
def test_check_process_status_running(
    mock_kill,
    client_process_manager,
    mock_client_run_registry,
    sample_client_run,
):
    mock_client_run_registry.get_by_id.return_value = sample_client_run

    result = client_process_manager.check_process_status(1)

    assert result is True
    mock_kill.assert_called_once_with(sample_client_run.pid, 0)


@patch("synchroagent.logic.client_process_manager.os.kill")
def test_check_process_status_not_found(
    mock_kill,
    client_process_manager,
    mock_client_run_registry,
    sample_client_run,
):
    mock_client_run_registry.get_by_id.return_value = sample_client_run
    mock_kill.side_effect = ProcessLookupError("No such process")

    result = client_process_manager.check_process_status(1)

    assert result is False
    mock_client_run_registry.update_run_status.assert_called_once()


def test_check_process_status_no_run(
    client_process_manager,
    mock_client_run_registry,
):
    mock_client_run_registry.get_by_id.return_value = None

    result = client_process_manager.check_process_status(1)

    assert result is False
