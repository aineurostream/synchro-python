import contextlib
import logging
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

from synchroagent.config import AppConfig

logger = logging.getLogger(__name__)

# Table creation statements
CREATE_CLIENTS_TABLE = """
CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    config_id INTEGER,
    FOREIGN KEY (config_id) REFERENCES configs (id)
)
"""

CREATE_CONFIGS_TABLE = """
CREATE TABLE IF NOT EXISTS configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    content TEXT NOT NULL,
    description TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

CREATE_REPORTS_TABLE = """
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    content TEXT,
    size INTEGER,
    generated_at TEXT NOT NULL,
    FOREIGN KEY (client_id) REFERENCES clients (id)
)
"""

CREATE_CLIENT_RUNS_TABLE = """
CREATE TABLE IF NOT EXISTS client_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    config_id INTEGER NOT NULL,
    report_id INTEGER,
    log_id INTEGER,
    pid INTEGER,
    status TEXT NOT NULL,
    output_dir TEXT,
    started_at TEXT,
    finished_at TEXT,
    exit_code INTEGER,
    FOREIGN KEY (client_id) REFERENCES clients (id),
    FOREIGN KEY (config_id) REFERENCES configs (id),
    FOREIGN KEY (report_id) REFERENCES reports (id)
)
"""

CREATE_LOGS_TABLE = """
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_run_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    log_type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (client_run_id) REFERENCES client_runs (id)
)
"""


class DatabaseConnection:
    def __init__(self, config: AppConfig) -> None:
        self.db_path = Path(config.db_path)
        self.connection: sqlite3.Connection | None = None
        self._connect()

    def _connect(self) -> None:
        try:
            self.connection = sqlite3.connect(
                self.db_path,
                detect_types=sqlite3.PARSE_DECLTYPES,
                check_same_thread=False,
            )
            if self.connection is None:
                raise ValueError("Failed to create database connection")

            self.connection.row_factory = sqlite3.Row
            self.connection.execute("PRAGMA foreign_keys = ON")
            self.connection.execute("PRAGMA journal_mode = WAL")
            self.connection.execute("PRAGMA synchronous = NORMAL")
            logger.info(f"Connected to database at {self.db_path}")
        except sqlite3.Error:
            logger.exception("Error connecting to database")
            raise

    def create_tables(self) -> None:
        if self.connection is None:
            raise ValueError("Database connection not initialized")

        try:
            with self.transaction():
                self.connection.execute(CREATE_CONFIGS_TABLE)
                self.connection.execute(CREATE_CLIENTS_TABLE)
                self.connection.execute(CREATE_REPORTS_TABLE)
                self.connection.execute(CREATE_CLIENT_RUNS_TABLE)
                self.connection.execute(CREATE_LOGS_TABLE)
            logger.info("Database tables created successfully")
        except sqlite3.Error:
            logger.exception("Error creating tables")
            raise

    @contextlib.contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        if self.connection is None:
            raise ValueError("Database connection not initialized")

        try:
            yield self.connection
            self.connection.commit()
        except Exception:
            if self.connection is not None:
                self.connection.rollback()
            logger.exception("Transaction rolled back due to error")
            raise

    def execute(self, query: str, params: tuple = ()) -> list[dict[str, Any]]:
        if self.connection is None:
            raise ValueError("Database connection not initialized")

        try:
            cursor = self.connection.cursor()
            cursor.execute(query, params)

            if query.strip().upper().startswith("SELECT"):
                return [dict(row) for row in cursor.fetchall()]

            self.connection.commit()
        except sqlite3.Error:
            if self.connection is not None:
                self.connection.rollback()
            logger.exception("Error executing query\n%s\n%s", query, params)
            raise
        else:
            return []

    def get_last_row_id(self) -> int:
        if self.connection is None:
            raise ValueError("Database connection not initialized")
        return cast(
            int,
            self.connection.execute(
                "SELECT last_insert_rowid()",
            ).fetchone()[0],
        )

    def close(self) -> None:
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.info("Database connection closed")

    def __del__(self) -> None:
        if hasattr(self, "connection") and self.connection is not None:
            self.close()


def get_db_connection(config: AppConfig | None = None) -> DatabaseConnection:
    if config is None:
        config = AppConfig()
    return DatabaseConnection(config)


@contextlib.contextmanager
def get_db_transaction() -> Iterator[DatabaseConnection]:
    db = get_db_connection()
    with db.transaction():
        yield db
