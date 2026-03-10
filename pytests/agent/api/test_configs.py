def test_get_configs(client, mock_config_registry, sample_config):
    mock_config_registry.get_all.return_value = [sample_config]

    response = client.get("/api/configs")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == 1
    assert response.json()[0]["name"] == "Test Config"
    assert response.json()[0]["content"] == {"key": "value"}
    mock_config_registry.get_all.assert_called_once()


def test_create_config(client, mock_config_registry, sample_config):
    mock_config_registry.create.return_value = sample_config

    response = client.post(
        "/api/configs",
        json={
            "name": "Test Config",
            "content": {"key": "value"},
            "description": "Test config description",
        },
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Test Config"
    assert response.json()["content"] == {"key": "value"}
    mock_config_registry.create.assert_called_once()


def test_get_config(client, mock_config_registry, sample_config):
    mock_config_registry.get_by_id.return_value = sample_config

    response = client.get("/api/configs/1")

    assert response.status_code == 200
    assert response.json()["id"] == 1
    assert response.json()["name"] == "Test Config"
    assert response.json()["content"] == {"key": "value"}
    mock_config_registry.get_by_id.assert_called_once_with(1)


def test_get_config_not_found(client, mock_config_registry):
    mock_config_registry.get_by_id.return_value = None

    response = client.get("/api/configs/999")

    assert response.status_code == 404
    mock_config_registry.get_by_id.assert_called_once_with(999)


def test_update_config(client, mock_config_registry, sample_config):
    mock_config_registry.get_by_id.return_value = sample_config
    mock_config_registry.update.return_value = sample_config

    response = client.put(
        "/api/configs/1",
        json={
            "name": "Updated Config",
            "content": {"updated_key": "updated_value"},
        },
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Test Config"  # Using the mock return value
    assert response.json()["content"] == {"key": "value"}  # Using the mock return value
    mock_config_registry.get_by_id.assert_called_once_with(1)
    mock_config_registry.update.assert_called_once()


def test_delete_config(
    client,
    mock_config_registry,
    mock_client_registry,
    sample_config,
):
    mock_config_registry.get_by_id.return_value = sample_config
    mock_client_registry.get_clients_by_config_id.return_value = []

    response = client.delete("/api/configs/1")

    assert response.status_code == 204
    mock_config_registry.get_by_id.assert_called_once_with(1)
    mock_client_registry.get_clients_by_config_id.assert_called_once_with(1)
    mock_config_registry.delete.assert_called_once_with(1)


def test_delete_config_with_clients(
    client,
    mock_config_registry,
    mock_client_registry,
    sample_config,
):
    mock_config_registry.get_by_id.return_value = sample_config
    mock_client_registry.get_clients_by_config_id.return_value = [
        {"id": 1, "name": "Client using this config"},
    ]

    response = client.delete("/api/configs/1")

    assert response.status_code == 400
    assert "Cannot delete config" in response.json()["detail"]
    mock_config_registry.get_by_id.assert_called_once_with(1)
    mock_client_registry.get_clients_by_config_id.assert_called_once_with(1)
    mock_config_registry.delete.assert_not_called()


def test_validate_config(client, mock_config_registry, sample_config):
    mock_config_registry.get_by_id.return_value = sample_config

    response = client.post("/api/configs/1/validate")

    assert response.status_code == 200
    assert "message" in response.json()
    assert response.json()["config_id"] == 1
    mock_config_registry.get_by_id.assert_called_once_with(1)


def test_validate_config_content(client):
    response = client.post(
        "/api/configs/validate",
        json={"key": "value"},
    )

    assert response.status_code == 200
    assert "message" in response.json()
    assert response.json()["config_id"] is None
