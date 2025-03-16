import pytest
from click.testing import CliRunner

from synchroagent.config import AppConfig


@pytest.fixture()
def cli_runner():
    return CliRunner()


@pytest.fixture()
def temp_config_file(tmp_path):
    config_path = tmp_path / "test_config.json"
    config_path.write_text('{"db_path": "test.db", "api_port": 9000}')
    return config_path


@pytest.fixture()
def test_config():
    return AppConfig(
        db_path="test.db",
        reports_dir="test-reports",
        outputs_dir="test-outputs",
        api_host="127.0.0.1",
        api_port=9000,
        hydra_script="test-hydra.py",
        synchro_report_script="test-report.py",
    )
