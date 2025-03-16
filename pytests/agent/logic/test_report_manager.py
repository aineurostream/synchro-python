import subprocess
from unittest.mock import MagicMock, mock_open, patch

from synchroagent.logic.report_manager import ReportManager


class TestReportManager:
    @patch("synchroagent.logic.report_manager.Path.mkdir")
    def test_init_creates_reports_dir(self, mock_mkdir):
        ReportManager(
            report_registry=MagicMock(),
            client_run_registry=MagicMock(),
            client_registry=MagicMock(),
            reports_dir="/tmp/test_reports",
        )
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    def test_generate_report_client_run_not_found(
        self,
        report_manager,
        mock_client_run_registry,
    ):
        mock_client_run_registry.get_by_id.return_value = None

        result = report_manager.generate_report(1)

        assert result is None
        mock_client_run_registry.get_by_id.assert_called_once_with(1)

    def test_generate_report_no_output_dir(
        self,
        report_manager,
        mock_client_run_registry,
        sample_client_run_stopped,
    ):
        run_without_output = sample_client_run_stopped.copy(update={"output_dir": None})
        mock_client_run_registry.get_by_id.return_value = run_without_output

        result = report_manager.generate_report(1)

        assert result is None
        mock_client_run_registry.get_by_id.assert_called_once_with(1)

    @patch.object(ReportManager, "_generate_report_file")
    def test_generate_report_file_generation_failed(
        self,
        mock_generate_file,
        report_manager,
        mock_client_run_registry,
        sample_client_run_stopped,
    ):
        mock_client_run_registry.get_by_id.return_value = sample_client_run_stopped
        mock_generate_file.return_value = None

        result = report_manager.generate_report(1)

        assert result is None
        mock_generate_file.assert_called_once_with(
            1,
            sample_client_run_stopped.output_dir,
        )

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="<html>Test Report</html>",
    )
    @patch.object(ReportManager, "_generate_report_file")
    def test_generate_report_success(
        self,
        mock_generate_file,
        mock_file,
        report_manager,
        mock_client_run_registry,
        mock_report_registry,
        sample_client_run_stopped,
        sample_report,
    ):
        mock_client_run_registry.get_by_id.return_value = sample_client_run_stopped
        mock_generate_file.return_value = "/tmp/test_reports/report_1_.html"
        mock_report_registry.create.return_value = 1
        mock_report_registry.get_by_id.return_value = sample_report

        result = report_manager.generate_report(1)

        assert result == sample_report
        mock_generate_file.assert_called_once_with(
            1,
            sample_client_run_stopped.output_dir,
        )
        mock_file.assert_called_once_with(
            "/tmp/test_reports/report_1_.html",
            encoding="utf-8",
        )
        mock_report_registry.create.assert_called_once()
        mock_client_run_registry.update.assert_called_once()

    @patch("builtins.open", side_effect=OSError("File read error"))
    @patch.object(ReportManager, "_generate_report_file")
    def test_generate_report_file_read_error(
        self,
        mock_generate_file,
        mock_file,
        report_manager,
        mock_client_run_registry,
        sample_client_run_stopped,
    ):
        mock_client_run_registry.get_by_id.return_value = sample_client_run_stopped
        mock_generate_file.return_value = "/tmp/test_reports/report_1_.html"

        result = report_manager.generate_report(1)

        assert result is None
        mock_generate_file.assert_called_once_with(
            1,
            sample_client_run_stopped.output_dir,
        )
        mock_file.assert_called_once_with(
            "/tmp/test_reports/report_1_.html",
            encoding="utf-8",
        )

    @patch("synchroagent.logic.report_manager.Path.is_file")
    def test_generate_report_file_script_not_found(
        self,
        mock_is_file,
        report_manager,
    ):
        mock_is_file.return_value = False

        result = report_manager._generate_report_file(1, "/tmp/test_outputs/run_1")

        assert result is None
        mock_is_file.assert_called_once()

    @patch("synchroagent.logic.report_manager.subprocess.run")
    @patch("synchroagent.logic.report_manager.Path.is_file")
    @patch("synchroagent.logic.report_manager.Path.exists")
    def test_generate_report_file_success(
        self,
        mock_exists,
        mock_is_file,
        mock_run,
        report_manager,
    ):
        mock_is_file.return_value = True
        mock_exists.return_value = True
        mock_process = MagicMock()
        mock_run.return_value = mock_process

        result = report_manager._generate_report_file(1, "/tmp/test_outputs/run_1")

        assert result == "/tmp/test_reports/report_1_.html"
        mock_run.assert_called_once()
        mock_exists.assert_called_once()

    @patch("synchroagent.logic.report_manager.subprocess.run")
    @patch("synchroagent.logic.report_manager.Path.is_file")
    @patch("synchroagent.logic.report_manager.Path.exists")
    def test_generate_report_file_not_created(
        self,
        mock_exists,
        mock_is_file,
        mock_run,
        report_manager,
    ):
        mock_is_file.return_value = True
        mock_exists.return_value = False
        mock_process = MagicMock()
        mock_run.return_value = mock_process

        result = report_manager._generate_report_file(1, "/tmp/test_outputs/run_1")

        assert result is None
        mock_run.assert_called_once()
        mock_exists.assert_called_once()

    @patch("synchroagent.logic.report_manager.subprocess.run")
    @patch("synchroagent.logic.report_manager.Path.is_file")
    def test_generate_report_file_subprocess_error(
        self,
        mock_is_file,
        mock_run,
        report_manager,
    ):
        mock_is_file.return_value = True
        mock_run.side_effect = subprocess.CalledProcessError(1, "cmd")

        result = report_manager._generate_report_file(1, "/tmp/test_outputs/run_1")

        assert result is None
        mock_run.assert_called_once()

    @patch("synchroagent.logic.report_manager.subprocess.run")
    @patch("synchroagent.logic.report_manager.Path.is_file")
    def test_generate_report_file_general_exception(
        self,
        mock_is_file,
        mock_run,
        report_manager,
    ):
        mock_is_file.return_value = True
        mock_run.side_effect = Exception("General error")

        result = report_manager._generate_report_file(1, "/tmp/test_outputs/run_1")

        assert result is None
        mock_run.assert_called_once()

    def test_get_report(
        self,
        report_manager,
        mock_report_registry,
        sample_report,
    ):
        mock_report_registry.get_by_id.return_value = sample_report

        result = report_manager.get_report(1)

        assert result == sample_report
        mock_report_registry.get_by_id.assert_called_once_with(1)

    def test_get_reports_by_client_id(
        self,
        report_manager,
        mock_report_registry,
        sample_report,
    ):
        mock_report_registry.get_reports_by_client_id.return_value = [sample_report]

        result = report_manager.get_reports_by_client_id(1)

        assert result == [sample_report]
        mock_report_registry.get_reports_by_client_id.assert_called_once_with(1)

    def test_get_report_for_client_run_no_run(
        self,
        report_manager,
        mock_client_run_registry,
    ):
        mock_client_run_registry.get_by_id.return_value = None

        result = report_manager.get_report_for_client_run(1)

        assert result is None
        mock_client_run_registry.get_by_id.assert_called_once_with(1)

    def test_get_report_for_client_run_no_report_id(
        self,
        report_manager,
        mock_client_run_registry,
        sample_client_run_stopped,
    ):
        mock_client_run_registry.get_by_id.return_value = sample_client_run_stopped

        result = report_manager.get_report_for_client_run(1)

        assert result is None
        mock_client_run_registry.get_by_id.assert_called_once_with(1)

    def test_get_report_for_client_run_success(
        self,
        report_manager,
        mock_client_run_registry,
        mock_report_registry,
        sample_client_run_stopped,
        sample_report,
    ):
        run_with_report = sample_client_run_stopped.copy(update={"report_id": 1})
        mock_client_run_registry.get_by_id.return_value = run_with_report
        mock_report_registry.get_by_id.return_value = sample_report

        result = report_manager.get_report_for_client_run(1)

        assert result == sample_report
        mock_client_run_registry.get_by_id.assert_called_once_with(1)
        mock_report_registry.get_by_id.assert_called_once_with(1)
