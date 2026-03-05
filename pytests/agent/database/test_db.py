from synchroagent.database.db import DatabaseConnection, get_db_connection


def test_database_connection_init(test_app_config):
    db = DatabaseConnection(test_app_config)
    assert db is not None
    db.close()


def test_database_connection_create_tables(db_connection):
    results = db_connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    table_names = [row["name"] for row in results]
    assert "clients" in table_names
    assert "configs" in table_names
    assert "reports" in table_names
    assert "client_runs" in table_names
    assert "logs" in table_names


def test_database_execute(db_connection):
    db_connection.execute(
        "INSERT INTO clients (name, description) VALUES (?, ?)",
        ("test_client", "Test description"),
    )
    results = db_connection.execute(
        "SELECT * FROM clients WHERE name = ?",
        ("test_client",),
    )
    assert len(results) == 1
    assert results[0]["name"] == "test_client"
    assert results[0]["description"] == "Test description"


def test_database_transaction_commit(db_connection):
    with db_connection.transaction() as conn:
        conn.execute(
            "INSERT INTO clients (name, description) VALUES (?, ?)",
            ("transaction_client", "Transaction test"),
        )
    results = db_connection.execute(
        "SELECT * FROM clients WHERE name = ?",
        ("transaction_client",),
    )
    assert len(results) == 1
    assert results[0]["name"] == "transaction_client"


def test_database_transaction_rollback(db_connection):
    try:
        with db_connection.transaction() as conn:
            conn.execute(
                "INSERT INTO clients (name, description) VALUES (?, ?)",
                ("rollback_client", "Rollback test"),
            )
            raise ValueError("Test exception to trigger rollback")
    except ValueError:
        pass
    results = db_connection.execute(
        "SELECT * FROM clients WHERE name = ?",
        ("rollback_client",),
    )
    assert len(results) == 0


def test_get_last_row_id(db_connection):
    db_connection.execute(
        "INSERT INTO clients (name, description) VALUES (?, ?)",
        ("row_id_client", "Row ID test"),
    )
    row_id = db_connection.get_last_row_id()
    assert row_id > 0
    results = db_connection.execute("SELECT * FROM clients WHERE id = ?", (row_id,))
    assert len(results) == 1
    assert results[0]["name"] == "row_id_client"


def test_get_db_connection(test_app_config):
    db = get_db_connection(test_app_config)
    assert db is not None
    assert isinstance(db, DatabaseConnection)
    db.close()
