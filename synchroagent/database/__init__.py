import logging
from functools import cache

from synchroagent.database.client_registry import ClientRegistry
from synchroagent.database.client_run_registry import ClientRunRegistry
from synchroagent.database.config_registry import ConfigRegistry
from synchroagent.database.db import DatabaseConnection, get_db_connection
from synchroagent.database.log_registry import LogRegistry
from synchroagent.database.report_registry import ReportRegistry

logger = logging.getLogger(__name__)


@cache
def init_database() -> DatabaseConnection:
    db = get_db_connection()
    db.create_tables()
    logger.info("Database initialized successfully")
    return db


@cache
def get_client_registry() -> ClientRegistry:
    return ClientRegistry(init_database())


@cache
def get_config_registry() -> ConfigRegistry:
    return ConfigRegistry(init_database())


@cache
def get_client_run_registry() -> ClientRunRegistry:
    return ClientRunRegistry(init_database())


@cache
def get_report_registry() -> ReportRegistry:
    return ReportRegistry(init_database())


@cache
def get_log_registry() -> LogRegistry:
    return LogRegistry(init_database())
