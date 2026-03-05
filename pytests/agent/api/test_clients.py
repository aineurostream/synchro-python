from unittest.mock import patch

from synchroagent.database.models import ClientSchema, ConfigSchema, RunStatus


def test_get_clients(client, mock_client_registry, sample_client):
    mock_client_registry.get_all.return_value = [sample_client]

    response = client.get("/api/clients")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == 1
    assert response.json()[0]["name"] == "Test Client"
    mock_client_registry.get_all.assert_called_once()


def test_create_client(client, mock_client_registry, sample_client):
    mock_client_registry.create.return_value = sample_client

    response = client.post(
        "/api/clients",
        json={
            "name": "Test Client",
            "description": "Test client description",
            "config_id": 1,
        },
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Test Client"
    mock_client_registry.create.assert_called_once()


def test_get_client(client, mock_client_registry, sample_client):
    mock_client_registry.get_by_id.return_value = sample_client

    response = client.get("/api/clients/1")

    assert response.status_code == 200
    assert response.json()["id"] == 1
    assert response.json()["name"] == "Test Client"
    mock_client_registry.get_by_id.assert_called_once_with(1)


def test_get_client_not_found(client, mock_client_registry):
    mock_client_registry.get_by_id.return_value = None

    response = client.get("/api/clients/999")

    assert response.status_code == 404
    mock_client_registry.get_by_id.assert_called_once_with(999)


def test_update_client(client, mock_client_registry, sample_client):
    mock_client_registry.get_by_id.return_value = sample_client
    mock_client_registry.update.return_value = sample_client

    response = client.put(
        "/api/clients/1",
        json={"name": "Updated Client"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Test Client"
    mock_client_registry.get_by_id.assert_called_once_with(1)
    mock_client_registry.update.assert_called_once()


def test_delete_client(client, mock_client_registry, mock_client_run_registry):
    mock_client_registry.get_by_id.return_value = ClientSchema(id=1, name="Test Client")
    mock_client_run_registry.get_active_runs_by_client_id.return_value = []
    mock_client_run_registry.get_runs_by_client_id.return_value = []

    response = client.delete("/api/clients/1")

    assert response.status_code == 204
    mock_client_registry.get_by_id.assert_called_once_with(1)
    mock_client_registry.delete.assert_called_once_with(1)


def test_get_client_runs(
    client,
    mock_client_registry,
    mock_client_run_registry,
    sample_client,
    sample_client_run,
):
    mock_client_registry.get_by_id.return_value = sample_client
    mock_client_run_registry.get_runs_by_client_id.return_value = [sample_client_run]

    response = client.get("/api/clients/1/runs")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == 1
    assert response.json()[0]["client_id"] == 1
    assert response.json()[0]["status"] == "running"
    mock_client_registry.get_by_id.assert_called_once_with(1)
    mock_client_run_registry.get_runs_by_client_id.assert_called_once_with(1)


def test_start_client_run(
    client,
    mock_client_registry,
    mock_client_process_manager,
    mock_config_registry,
    sample_client,
    sample_client_run,
):
    mock_client_registry.reset_mock()
    mock_client_process_manager.reset_mock()
    mock_config_registry.reset_mock()

    mock_client_registry.get_by_id.return_value = sample_client
    mock_config_registry.get_by_id.return_value = ConfigSchema(
        id=1,
        name="Test Config",
        content={},
    )

    mock_client_process_manager.start_client.return_value = sample_client_run

    with patch(
        "synchroagent.api.clients.ClientProcessManager.start_client",
    ) as mock_start:
        mock_start.return_value = sample_client_run

        response = client.post(
            "/api/clients/1/runs",
            json={"config_id": 1},
        )

        assert response.status_code == 201
        assert response.json()["client_id"] == 1
        assert response.json()["status"] == "running"
        mock_client_registry.get_by_id.assert_called_with(1)
        mock_start.assert_called_once()


def test_get_client_run(
    client,
    mock_client_registry,
    mock_client_run_registry,
    sample_client,
    sample_client_run,
):
    mock_client_registry.get_by_id.return_value = sample_client
    mock_client_run_registry.get_by_id.return_value = sample_client_run

    response = client.get("/api/clients/1/runs/1")

    assert response.status_code == 200
    assert response.json()["id"] == 1
    assert response.json()["client_id"] == 1
    assert response.json()["status"] == "running"
    mock_client_registry.get_by_id.assert_called_once_with(1)
    mock_client_run_registry.get_by_id.assert_called_once_with(1)


def test_stop_client_run(
    client,
    mock_client_registry,
    mock_client_run_registry,
    mock_client_process_manager,
    sample_client,
    sample_client_run,
):
    mock_client_registry.reset_mock()
    mock_client_run_registry.reset_mock()
    mock_client_process_manager.reset_mock()

    mock_client_registry.get_by_id.return_value = sample_client
    mock_client_run_registry.get_by_id.return_value = sample_client_run

    mock_client_process_manager.stop_client_run.return_value = sample_client_run

    with patch(
        "synchroagent.api.clients.ClientProcessManager.stop_client_run",
    ) as mock_stop:
        mock_stop.return_value = sample_client_run

        response = client.delete("/api/clients/1/runs/1")

        assert response.status_code == 204
        mock_client_registry.get_by_id.assert_called_with(1)
        assert mock_client_run_registry.get_by_id.call_args_list[0] == ((1,),)
        mock_stop.assert_called_once_with(1)


def test_get_client_run_logs(
    client,
    mock_client_registry,
    mock_client_run_registry,
    mock_log_registry,
    mock_log_manager,
    sample_client,
    sample_client_run,
    sample_log,
):
    mock_client_registry.get_by_id.return_value = sample_client
    sample_client_run.log_id = 1
    mock_client_run_registry.get_by_id.return_value = sample_client_run
    mock_log_registry.get_by_id.return_value = sample_log

    response = client.get("/api/clients/1/runs/1/logs")

    assert response.status_code == 200
    assert response.json()["id"] == 1
    assert response.json()["content"] == "Test log content"
    assert response.json()["log_type"] == "stdout"
    mock_client_registry.get_by_id.assert_called_once_with(1)
    mock_client_run_registry.get_by_id.assert_called_once_with(1)


def test_get_client_reports(
    client,
    mock_client_registry,
    mock_report_registry,
    sample_client,
    sample_report,
):
    mock_client_registry.get_by_id.return_value = sample_client
    mock_report_registry.get_reports_by_client_id.return_value = [sample_report]

    response = client.get("/api/clients/1/reports")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == 1
    assert response.json()[0]["client_id"] == 1
    assert response.json()[0]["content"] == "<html>Test report content</html>"
    mock_client_registry.get_by_id.assert_called_once_with(1)
    mock_report_registry.get_reports_by_client_id.assert_called_once_with(1)


def test_get_client_run_report(
    client,
    mock_client_registry,
    mock_client_run_registry,
    mock_report_registry,
    mock_report_manager,
    sample_client,
    sample_client_run,
    sample_report,
):
    mock_client_registry.get_by_id.return_value = sample_client
    sample_client_run.report_id = 1
    mock_client_run_registry.get_by_id.return_value = sample_client_run
    mock_report_registry.get_by_id.return_value = sample_report

    response = client.get("/api/clients/1/runs/1/report")

    assert response.status_code == 200
    assert response.json()["id"] == 1
    assert response.json()["client_id"] == 1
    assert response.json()["content"] == "<html>Test report content</html>"
    mock_client_registry.get_by_id.assert_called_once_with(1)
    mock_client_run_registry.get_by_id.assert_called_once_with(1)


def test_generate_client_run_report(
    client,
    mock_client_registry,
    mock_client_run_registry,
    mock_report_registry,
    mock_report_manager,
    sample_client,
    sample_client_run,
    sample_report,
):
    mock_client_registry.get_by_id.return_value = sample_client

    sample_client_run.status = RunStatus.STOPPED
    mock_client_run_registry.get_by_id.return_value = sample_client_run
    mock_report_registry.get_by_id.return_value = sample_report

    with patch(
        "synchroagent.api.clients.ReportManager.generate_report",
    ) as mock_generate:
        mock_generate.return_value = 1

        response = client.post("/api/clients/1/runs/1/report")

        assert response.status_code == 200
        assert response.json()["id"] == 1
        assert response.json()["client_id"] == 1
        assert response.json()["content"] == "<html>Test report content</html>"
        mock_client_registry.get_by_id.assert_called_once_with(1)
        mock_client_run_registry.get_by_id.assert_called_once_with(1)
        mock_generate.assert_called_once_with(1)
