import logging
import subprocess
from pathlib import Path

from synchroagent.config import default_config
from synchroagent.database.client_registry import ClientRegistry
from synchroagent.database.client_run_registry import ClientRunRegistry, ClientRunUpdate
from synchroagent.database.models import ReportSchema
from synchroagent.database.report_registry import ReportCreate, ReportRegistry

logger = logging.getLogger(__name__)


class ReportManager:
    def __init__(
        self,
        report_registry: ReportRegistry,
        client_run_registry: ClientRunRegistry,
        client_registry: ClientRegistry,
        reports_dir: str | None = None,
    ) -> None:
        self.report_registry = report_registry
        self.client_run_registry = client_run_registry
        self.client_registry = client_registry
        self.reports_dir = reports_dir or default_config.reports_dir
        self.synchro_report_script = default_config.synchro_report_script
        Path(self.reports_dir).mkdir(parents=True, exist_ok=True)

    def generate_report(self, client_run_id: int) -> ReportSchema:
        client_run = self.client_run_registry.get_by_id(client_run_id)
        if not client_run:
            raise ValueError(f"Client run not found: {client_run_id}")

        if not client_run.output_dir:
            raise ValueError(f"Client run has no output directory: {client_run_id}")

        report_path = self._generate_report_file(client_run_id, client_run.output_dir)
        if not report_path:
            raise ValueError(
                f"Failed to generate report file for client run: {client_run_id}",
            )

        try:
            with open(report_path, encoding="utf-8") as f:
                report_content = f.read()
        except Exception as e:
            raise ValueError(f"Failed to read report file: {report_path}") from e

        report_create = ReportCreate(
            client_id=client_run.client_id,
            content=report_content,
        )

        report_id = self.report_registry.create(report_create)
        if not report_id:
            raise ValueError("Failed to create report record in database")

        client_run_update = ClientRunUpdate(report_id=report_id)
        self.client_run_registry.update(client_run_id, client_run_update)

        final_report = self.report_registry.get_by_id(report_id)
        if not final_report:
            raise ValueError("Failed to get report from database")

        return final_report

    def _generate_report_file(self, client_run_id: int, output_dir: str) -> str | None:
        report_script_path = Path(self.synchro_report_script).resolve()
        if not report_script_path.is_file():
            logger.error(f"Report script not found: {report_script_path}")
            return None

        report_filename = f"report_{client_run_id}_.html"
        report_path = Path(self.reports_dir) / report_filename

        try:
            subprocess.run(
                [  # noqa: S607
                    "python3",
                    str(report_script_path),
                    "generate",
                    output_dir,
                    str(report_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )

            if not report_path.exists():
                logger.error(f"Report file was not created: {report_path}")
                return None

            return str(report_path)
        except subprocess.CalledProcessError:
            logger.exception("Report generation failed")
            return None
        except Exception:
            logger.exception("Error generating report")
            return None

    def get_report(self, report_id: int) -> ReportSchema | None:
        return self.report_registry.get_by_id(report_id)

    def get_reports_by_client_id(self, client_id: int) -> list[ReportSchema]:
        return self.report_registry.get_reports_by_client_id(client_id)

    def get_report_for_client_run(self, client_run_id: int) -> ReportSchema | None:
        client_run = self.client_run_registry.get_by_id(client_run_id)
        if not client_run or not client_run.report_id:
            return None

        return self.report_registry.get_by_id(client_run.report_id)
