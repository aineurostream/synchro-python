from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from synchroagent.logic.log_manager import LogManager


def test_collect_logs_client_run_not_found(
    log_manager,
    mock_client_run_registry,
):
    mock_client_run_registry.get_by_id.return_value = None

    with pytest.raises(ValueError, match="Client run not found: 1"):
        log_manager.collect_logs(1)

    mock_client_run_registry.get_by_id.assert_called_once_with(1)


def test_collect_logs_no_output_dir(
    log_manager,
    mock_client_run_registry,
    sample_client_run_stopped,
):
    run_without_output = sample_client_run_stopped.copy(update={"output_dir": None})
    mock_client_run_registry.get_by_id.return_value = run_without_output

    with pytest.raises(ValueError, match="Client run has no output directory: 1"):
        log_manager.collect_logs(1)

    mock_client_run_registry.get_by_id.assert_called_once_with(1)


@patch("synchroagent.logic.log_manager.Path.exists")
def test_collect_logs_output_dir_not_found(
    mock_exists,
    log_manager,
    mock_client_run_registry,
    sample_client_run_stopped,
):
    mock_client_run_registry.get_by_id.return_value = sample_client_run_stopped
    mock_exists.return_value = False

    with pytest.raises(ValueError, match="Output directory not found:"):
        log_manager.collect_logs(1)

    mock_client_run_registry.get_by_id.assert_called_once_with(1)
    mock_exists.assert_called_once()


@patch("synchroagent.logic.log_manager.Path.exists")
def test_collect_logs_log_file_not_found(
    mock_exists,
    log_manager,
    mock_client_run_registry,
    sample_client_run_stopped,
):
    mock_client_run_registry.get_by_id.return_value = sample_client_run_stopped
    mock_exists.side_effect = [True, False]

    with pytest.raises(ValueError, match="No log file found in"):
        log_manager.collect_logs(1)

    mock_client_run_registry.get_by_id.assert_called_once_with(1)
    assert mock_exists.call_count == 2


@patch("synchroagent.logic.log_manager.Path.exists")
@patch.object(LogManager, "_read_log_file")
def test_collect_logs_success(
    mock_read_log,
    mock_exists,
    log_manager,
    mock_client_run_registry,
    mock_log_registry,
    sample_client_run_stopped,
):
    mock_client_run_registry.get_by_id.return_value = sample_client_run_stopped
    mock_exists.return_value = True
    mock_read_log.return_value = "Log content"
    mock_log = MagicMock()
    mock_log.id = 1
    mock_log_registry.create.return_value = mock_log

    log_id = log_manager.collect_logs(1)

    assert log_id == 1
    mock_client_run_registry.get_by_id.assert_called_once_with(1)
    mock_exists.assert_called()
    mock_read_log.assert_called_once()
    mock_log_registry.create.assert_called_once()
    mock_client_run_registry.update.assert_called_once()


@patch("synchroagent.logic.log_manager.Path.exists")
@patch.object(LogManager, "_read_log_file")
def test_collect_logs_create_failed(
    mock_read_log,
    mock_exists,
    log_manager,
    mock_client_run_registry,
    mock_log_registry,
    sample_client_run_stopped,
):
    mock_client_run_registry.get_by_id.return_value = sample_client_run_stopped
    mock_exists.return_value = True
    mock_read_log.return_value = "Log content"
    mock_log_registry.create.return_value = None

    with pytest.raises(ValueError, match="Failed to create log record in database"):
        log_manager.collect_logs(1)

    mock_client_run_registry.get_by_id.assert_called_once_with(1)
    mock_exists.assert_called()
    mock_read_log.assert_called_once()
    mock_log_registry.create.assert_called_once()
    mock_client_run_registry.update.assert_not_called()


def test_read_log_file_success(log_manager, tmp_path):
    log_file = tmp_path / "hydra.log"
    log_file.write_text("Log content", encoding="utf-8")

    result = log_manager._read_log_file(log_file)

    assert result == "Log content"


@patch.object(Path, "open", side_effect=OSError("File read error"))
def test_read_log_file_error(mock_open_method, log_manager):
    log_file = Path("/tmp/test_outputs/run_1/.hydra/hydra.log")

    with pytest.raises(ValueError, match="Failed to read log file:"):
        log_manager._read_log_file(log_file)


def test_get_log(log_manager, mock_log_registry, sample_log):
    mock_log_registry.get_by_id.return_value = sample_log

    result = log_manager.get_log(1)

    assert result == sample_log
    mock_log_registry.get_by_id.assert_called_once_with(1)


def test_get_log_not_found(log_manager, mock_log_registry):
    mock_log_registry.get_by_id.return_value = None

    result = log_manager.get_log(1)

    assert result is None
    mock_log_registry.get_by_id.assert_called_once_with(1)


def test_get_logs_by_client_run(log_manager, mock_log_registry, sample_log):
    mock_log_registry.get_logs_by_client_run.return_value = [sample_log]

    result = log_manager.get_logs_by_client_run(1)

    assert result == [sample_log]
    mock_log_registry.get_logs_by_client_run.assert_called_once_with(1)
