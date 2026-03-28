import uuid
from unittest.mock import MagicMock, patch


@patch("uuid.uuid4")
def test_save_config_to_file(
    mock_uuid4,
    client_process_manager,
    sample_config,
    tmp_path,
):
    assert tmp_path.exists()
    mock_uuid4.return_value = uuid.UUID("12345678-1234-1234-1234-123456789abc")

    with patch("synchroagent.logic.client_process_manager.Path") as mock_path:
        mock_pipeline_dir = mock_path.return_value
        mock_mkdir = mock_pipeline_dir.mkdir = MagicMock()

        mock_config_path = mock_pipeline_dir / "agent_test_config_12345678.yaml"
        mock_file = MagicMock()
        mock_config_path.open.return_value.__enter__ = MagicMock(
            return_value=mock_file,
        )
        mock_config_path.open.return_value.__exit__ = MagicMock(return_value=False)

        config_filename = client_process_manager._save_config_to_file(
            sample_config,
            1,
        )

        assert config_filename == "agent_test_config_12345678.yaml"

        mock_mkdir.assert_called_once_with(
            parents=True,
            exist_ok=True,
        )
