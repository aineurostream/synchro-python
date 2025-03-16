from functools import cache
from typing import Annotated

from fastapi import Depends

from synchroagent.config import AppConfig, default_config
from synchroagent.database import (
    get_client_registry,
    get_client_run_registry,
    get_config_registry,
    get_log_registry,
    get_report_registry,
    init_database,
)
from synchroagent.database.client_registry import ClientRegistry
from synchroagent.database.client_run_registry import ClientRunRegistry
from synchroagent.database.config_registry import ConfigRegistry
from synchroagent.database.db import DatabaseConnection
from synchroagent.database.log_registry import LogRegistry
from synchroagent.database.report_registry import ReportRegistry
from synchroagent.logic.client_process_manager import ClientProcessManager
from synchroagent.logic.log_manager import LogManager
from synchroagent.logic.report_manager import ReportManager


@cache
def get_app_config() -> AppConfig:
    return default_config


def get_db() -> DatabaseConnection:
    return init_database()


def get_client_registry_dep() -> ClientRegistry:
    return get_client_registry()


def get_config_registry_dep() -> ConfigRegistry:
    return get_config_registry()


def get_client_run_registry_dep() -> ClientRunRegistry:
    return get_client_run_registry()


def get_report_registry_dep() -> ReportRegistry:
    return get_report_registry()


def get_log_registry_dep() -> LogRegistry:
    return get_log_registry()


def get_client_process_manager(
    client_registry: Annotated[ClientRegistry, Depends(get_client_registry_dep)],
    client_run_registry: Annotated[
        ClientRunRegistry,
        Depends(get_client_run_registry_dep),
    ],
    config_registry: Annotated[ConfigRegistry, Depends(get_config_registry_dep)],
    app_config: Annotated[AppConfig, Depends(get_app_config)],
) -> ClientProcessManager:
    return ClientProcessManager(
        client_registry=client_registry,
        client_run_registry=client_run_registry,
        config_registry=config_registry,
        outputs_dir=app_config.outputs_dir,
    )


def get_log_manager(
    log_registry: Annotated[LogRegistry, Depends(get_log_registry_dep)],
    client_run_registry: Annotated[
        ClientRunRegistry,
        Depends(get_client_run_registry_dep),
    ],
) -> LogManager:
    return LogManager(
        log_registry=log_registry,
        client_run_registry=client_run_registry,
    )


def get_report_manager(
    report_registry: Annotated[ReportRegistry, Depends(get_report_registry_dep)],
    client_run_registry: Annotated[
        ClientRunRegistry,
        Depends(get_client_run_registry_dep),
    ],
    client_registry: Annotated[ClientRegistry, Depends(get_client_registry_dep)],
    app_config: Annotated[AppConfig, Depends(get_app_config)],
) -> ReportManager:
    return ReportManager(
        report_registry=report_registry,
        client_run_registry=client_run_registry,
        client_registry=client_registry,
        reports_dir=app_config.reports_dir,
    )
