import uuid
from unittest.mock import MagicMock, patch

from synchroagent.logic.client_process_manager import ClientProcessManager


@patch("uuid.uuid4")
def test_save_config_to_file(
    mock_uuid4,
    client_process_manager,
    sample_config,
    tmp_path,
):
    mock_uuid4.return_value = uuid.UUID("12345678-1234-1234-1234-123456789abc")

    with patch("synchroagent.logic.client_process_manager.Path") as mock_path:
        mock_pipeline_dir = mock_path.return_value
        mock_mkdir = mock_pipeline_dir.mkdir = MagicMock()

        with patch("builtins.open", create=True) as mock_open:
            mock_open_instance = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_open_instance

            config_filename = client_process_manager._save_config_to_file(
                sample_config,
                1,
            )

            assert config_filename == "agent_test_config_12345678.yaml"

            mock_mkdir.assert_called_once_with(
                parents=True,
                exist_ok=True,
            )

            mock_open.assert_called_once()

            args = mock_open.call_args[0]
            assert str(
                mock_pipeline_dir / "agent_test_config_12345678.yaml",
            ) in str(args[0])

            assert mock_open_instance.write.call_count > 0


@patch("synchroagent.logic.client_process_manager.subprocess.Popen")
@patch("synchroagent.logic.client_process_manager.Path.is_file")
@patch.object(ClientProcessManager, "_save_config_to_file")
def test_start_process_uses_saved_config(
    mock_save_config,
    mock_is_file,
    mock_popen,
    client_process_manager,
    mock_client_run_registry,
    sample_config,
    sample_client_run,
):
    mock_is_file.return_value = True
    mock_process = mock_popen.return_value
    mock_process.pid = 12345
    mock_client_run_registry.get_by_id.return_value = sample_client_run
    mock_save_config.return_value = "agent_test_config_12345678.yaml"

    client_process_manager._start_process(sample_config, 1)

    mock_save_config.assert_called_once_with(sample_config, 1)

    mock_popen.assert_called_once()
    args, _ = mock_popen.call_args
    cmd = args[0]

    assert "pipeline=agent_test_config_12345678" in cmd
