import queue
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from synchroagent.database.models import RunStatus
from synchroagent.logic.client_process_monitor import ClientProcessMonitor, ProcessInfo


@pytest.fixture()
def mock_client_run_registry():
    return MagicMock()


@pytest.fixture()
def process_monitor(mock_client_run_registry):
    monitor = ClientProcessMonitor(
        client_run_registry=mock_client_run_registry,
        poll_interval=0.1,
    )
    yield monitor
    monitor.stop()


def test_init(process_monitor, mock_client_run_registry):
    """Test monitor initialization."""
    assert process_monitor.client_run_registry == mock_client_run_registry
    assert process_monitor.poll_interval == 0.1
    assert isinstance(process_monitor.processes, dict)
    assert isinstance(process_monitor.process_queue, queue.Queue)
    assert process_monitor.running is True
    assert isinstance(process_monitor.lock, type(threading.RLock()))
    assert isinstance(process_monitor.completed_outputs, dict)


def test_register_process(process_monitor):
    """Test registering a process."""
    mock_process = MagicMock()
    mock_process.pid = 12345

    process_monitor.register_process(1, mock_process)

    assert process_monitor.process_queue.qsize() == 1

    process_info = process_monitor.process_queue.get()
    assert process_info.run_id == 1
    assert process_info.process == mock_process
    assert process_info.stdout_buffer == ""
    assert process_info.stderr_buffer == ""
    assert isinstance(process_info.last_check_time, float)


@patch("synchroagent.logic.client_process_monitor.select.select")
def test_read_pipe_nonblocking_data_available(mock_select, process_monitor):
    """Test reading from a pipe when data is available."""
    mock_pipe = MagicMock()
    mock_pipe.read.return_value = "Test output"
    mock_select.return_value = ([mock_pipe], [], [])

    output = process_monitor._read_pipe_nonblocking(mock_pipe)

    assert output == "Test output"
    mock_pipe.read.assert_called_once()


@patch("synchroagent.logic.client_process_monitor.select.select")
def test_read_pipe_nonblocking_no_data(mock_select, process_monitor):
    """Test reading from a pipe when no data is available."""
    mock_pipe = MagicMock()
    mock_select.return_value = ([], [], [])

    output = process_monitor._read_pipe_nonblocking(mock_pipe)

    assert output == ""
    mock_pipe.read.assert_not_called()


def test_store_process_outputs(process_monitor):
    """Test storing process outputs."""
    process_info = ProcessInfo(
        run_id=1,
        process=MagicMock(),
        stdout_buffer="Stdout content",
        stderr_buffer="Stderr content",
    )

    process_monitor._store_process_outputs(process_info)

    assert 1 in process_monitor.completed_outputs
    assert process_monitor.completed_outputs[1]["stdout"] == "Stdout content"
    assert process_monitor.completed_outputs[1]["stderr"] == "Stderr content"


def test_handle_process_exit_success(process_monitor, mock_client_run_registry):
    """Test handling a process that exits successfully."""
    process_info = ProcessInfo(
        run_id=1,
        process=MagicMock(),
    )

    process_monitor._handle_process_exit(process_info, 0)

    mock_client_run_registry.update.assert_called_once()
    update_args = mock_client_run_registry.update.call_args[0]
    assert update_args[0] == 1
    update_obj = update_args[1]
    assert update_obj.status == RunStatus.STOPPED
    assert update_obj.exit_code == 0


def test_handle_process_exit_failure(process_monitor, mock_client_run_registry):
    """Test handling a process that exits with an error."""
    process_info = ProcessInfo(
        run_id=1,
        process=MagicMock(),
    )

    process_monitor._handle_process_exit(process_info, 1)

    mock_client_run_registry.update.assert_called_once()
    update_args = mock_client_run_registry.update.call_args[0]
    assert update_args[0] == 1
    update_obj = update_args[1]
    assert update_obj.status == RunStatus.FAILED
    assert update_obj.exit_code == 1


@patch.object(ClientProcessMonitor, "_read_process_output")
@patch.object(ClientProcessMonitor, "_store_process_outputs")
@patch.object(ClientProcessMonitor, "_handle_process_exit")
def test_monitor_process_running(
    mock_handle_exit,
    mock_store_outputs,
    mock_read_output,
    process_monitor,
):
    """Test monitoring a running process."""
    mock_process = MagicMock()
    mock_process.poll.return_value = None

    process_info = ProcessInfo(
        run_id=1,
        process=mock_process,
        last_check_time=time.time() - 1,
    )
    with process_monitor.lock:
        process_monitor.processes[1] = process_info
    process_monitor._monitor_process(process_info)

    mock_read_output.assert_called_once_with(process_info)
    mock_store_outputs.assert_not_called()
    mock_handle_exit.assert_not_called()

    assert 1 in process_monitor.processes


@patch.object(ClientProcessMonitor, "_read_process_output")
@patch.object(ClientProcessMonitor, "_store_process_outputs")
@patch.object(ClientProcessMonitor, "_handle_process_exit")
def test_monitor_process_exited(
    mock_handle_exit,
    mock_store_outputs,
    mock_read_output,
    process_monitor,
):
    """Test monitoring a process that has exited."""
    mock_process = MagicMock()
    mock_process.poll.return_value = 0

    process_info = ProcessInfo(
        run_id=1,
        process=mock_process,
    )

    with process_monitor.lock:
        process_monitor.processes[1] = process_info

    process_monitor._monitor_process(process_info)

    mock_read_output.assert_called_once_with(process_info)
    mock_store_outputs.assert_called_once_with(process_info)
    mock_handle_exit.assert_called_once_with(process_info, 0)

    assert 1 not in process_monitor.processes


def test_check_new_processes(process_monitor):
    """Test checking for new processes in the queue."""

    mock_process1 = MagicMock()
    mock_process2 = MagicMock()

    process_monitor.register_process(1, mock_process1)
    process_monitor.register_process(2, mock_process2)

    process_monitor._check_new_processes()

    assert 1 in process_monitor.processes
    assert 2 in process_monitor.processes
    assert process_monitor.processes[1].run_id == 1
    assert process_monitor.processes[1].process == mock_process1
    assert process_monitor.processes[2].run_id == 2
    assert process_monitor.processes[2].process == mock_process2


def test_get_process_output_completed(process_monitor):
    """Test getting output for a completed process."""

    process_monitor.completed_outputs[1] = {
        "stdout": "Completed stdout",
        "stderr": "Completed stderr",
    }

    output = process_monitor.get_process_output(1)

    assert output["stdout"] == "Completed stdout"
    assert output["stderr"] == "Completed stderr"


def test_get_process_output_running(process_monitor):
    """Test getting output for a running process."""

    mock_process = MagicMock()
    process_info = ProcessInfo(
        run_id=1,
        process=mock_process,
        stdout_buffer="Running stdout",
        stderr_buffer="Running stderr",
    )

    with process_monitor.lock:
        process_monitor.processes[1] = process_info

    output = process_monitor.get_process_output(1)

    assert output["stdout"] == "Running stdout"
    assert output["stderr"] == "Running stderr"


def test_get_process_output_not_found(process_monitor):
    """Test getting output for a non-existent process."""
    output = process_monitor.get_process_output(999)

    assert output["stdout"] == ""
    assert output["stderr"] == ""


def test_is_process_running(process_monitor):
    """Test checking if a process is running."""

    mock_process = MagicMock()
    process_info = ProcessInfo(
        run_id=1,
        process=mock_process,
    )

    with process_monitor.lock:
        process_monitor.processes[1] = process_info

    assert process_monitor.is_process_running(1) is True
    assert process_monitor.is_process_running(999) is False


def test_set_process_completed_callback(process_monitor):
    """Test that the callback is correctly set."""
    callback = MagicMock()
    process_monitor.set_process_completed_callback(callback)
    assert process_monitor.on_process_completed == callback


@patch(
    "synchroagent.logic.client_process_monitor.ClientProcessMonitor._store_process_outputs",
)
@patch(
    "synchroagent.logic.client_process_monitor.ClientProcessMonitor._handle_process_exit",
)
def test_callback_invocation(
    mock_handle_exit,
    mock_store_outputs,
    process_monitor,
):
    """Test that the callback is invoked when a process completes."""
    callback = MagicMock()
    process_monitor.set_process_completed_callback(callback)

    run_id = 42
    exit_code = 0
    process = MagicMock()
    process.poll.return_value = exit_code

    process_info = ProcessInfo(run_id=run_id, process=process)
    process_monitor.processes[run_id] = process_info

    process_monitor._monitor_process(process_info)

    callback.assert_called_once_with(run_id, exit_code)
