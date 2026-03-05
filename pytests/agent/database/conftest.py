import sqlite3
from collections.abc import Generator

import pytest

from synchroagent.config import AppConfig
from synchroagent.database.client_registry import ClientCreate, ClientRegistry
from synchroagent.database.client_run_registry import ClientRunCreate, ClientRunRegistry
from synchroagent.database.config_registry import ConfigCreate, ConfigRegistry
from synchroagent.database.db import DatabaseConnection
from synchroagent.database.log_registry import LogRegistry
from synchroagent.database.models import RunStatus
from synchroagent.database.report_registry import ReportRegistry


@pytest.fixture()
def test_db_path() -> str:
    return ":memory:"


@pytest.fixture()
def test_app_config(test_db_path: str) -> AppConfig:
    return AppConfig(
        db_path=test_db_path,
        log_level="DEBUG",
    )


@pytest.fixture()
def db_connection(
    test_app_config: AppConfig,
) -> Generator[DatabaseConnection, None, None]:
    conn = DatabaseConnection(test_app_config)
    conn.create_tables()
    yield conn
    conn.close()


@pytest.fixture()
def db_transaction(
    db_connection: DatabaseConnection,
) -> Generator[sqlite3.Connection, None, None]:
    with db_connection.transaction() as transaction:
        yield transaction


@pytest.fixture()
def config_registry(db_connection):
    return ConfigRegistry(db_connection)


@pytest.fixture()
def client_registry(db_connection):
    return ClientRegistry(db_connection)


@pytest.fixture()
def client_run_registry(db_connection):
    return ClientRunRegistry(db_connection)


@pytest.fixture()
def log_registry(db_connection):
    return LogRegistry(db_connection)


@pytest.fixture()
def report_registry(db_connection):
    return ReportRegistry(db_connection)


@pytest.fixture()
def test_config_item(config_registry):
    config = ConfigCreate(
        name="report_test_config",
        content={"key": "value"},
    )
    return config_registry.create(config)


@pytest.fixture()
def test_client_item(client_registry, test_config_item):
    client = ClientCreate(
        name="run_test_client",
        config_id=test_config_item.id,
    )
    return client_registry.create(client)


@pytest.fixture()
def test_client_run_item(client_run_registry, test_client_item, test_config_item):
    client_run = ClientRunCreate(
        client_id=test_client_item.id,
        config_id=test_config_item.id,
        status=RunStatus.CREATED,
    )
    return client_run_registry.create(client_run)
