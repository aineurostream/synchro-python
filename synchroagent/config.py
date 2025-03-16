import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


DEFAULT_DB_PATH = "synchroagent.db"
DEFAULT_REPORTS_DIR = "reports"
DEFAULT_HYDRA_SCRIPT = "hydra_run.py"
DEFAULT_OUTPUTS_DIR = "outputs"
DEFAULT_SYNCHRO_REPORT_SCRIPT = "../synchro_reporter.git/report.py"
DEFAULT_API_HOST = "0.0.0.0"  # noqa: S104
DEFAULT_API_PORT = 8000


class AppConfig(BaseModel):
    db_path: str = Field(
        default_factory=lambda: os.environ.get("AGNT_DB_PATH", DEFAULT_DB_PATH),
    )
    reports_dir: str = Field(
        default_factory=lambda: os.environ.get("AGNT_REPORTS_DIR", DEFAULT_REPORTS_DIR),
    )
    hydra_script: str = Field(
        default_factory=lambda: os.environ.get(
            "AGNT_HYDRA_SCRIPT",
            DEFAULT_HYDRA_SCRIPT,
        ),
    )
    outputs_dir: str = Field(
        default_factory=lambda: os.environ.get("AGNT_OUTPUTS_DIR", DEFAULT_OUTPUTS_DIR),
    )
    synchro_report_script: str = Field(
        default_factory=lambda: os.environ.get(
            "AGNT_SYNCHRO_REPORT_SCRIPT",
            DEFAULT_SYNCHRO_REPORT_SCRIPT,
        ),
    )
    api_host: str = Field(
        default_factory=lambda: os.environ.get("AGNT_API_HOST", DEFAULT_API_HOST),
    )
    api_port: int = Field(
        default_factory=lambda: int(os.environ.get("AGNT_API_PORT", DEFAULT_API_PORT)),
    )


default_config = AppConfig()
