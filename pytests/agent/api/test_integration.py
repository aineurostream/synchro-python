import time


def test_create_and_get_config(integration_client):
    timestamp = int(time.time())
    config_data = {
        "name": f"Integration Test Config {timestamp}",
        "content": {"test_key": "test_value"},
        "description": "Config for integration testing",
    }

    create_response = integration_client.post("/api/configs", json=config_data)
    assert create_response.status_code == 201

    config_id = create_response.json()["id"]

    get_response = integration_client.get(f"/api/configs/{config_id}")
    assert get_response.status_code == 200
    assert get_response.json()["name"] == f"Integration Test Config {timestamp}"
    assert get_response.json()["content"] == {"test_key": "test_value"}


def test_create_and_get_client(integration_client):
    timestamp = int(time.time())
    config_data = {
        "name": f"Client Test Config {timestamp}",
        "content": {"test_key": "test_value"},
    }

    config_response = integration_client.post("/api/configs", json=config_data)
    assert config_response.status_code == 201

    config_id = config_response.json()["id"]

    client_data = {
        "name": f"Integration Test Client {timestamp}",
        "description": "Client for integration testing",
        "config_id": config_id,
    }

    create_response = integration_client.post("/api/clients", json=client_data)
    assert create_response.status_code == 201

    client_id = create_response.json()["id"]

    get_response = integration_client.get(f"/api/clients/{client_id}")
    assert get_response.status_code == 200
    assert get_response.json()["name"] == f"Integration Test Client {timestamp}"
    assert get_response.json()["config_id"] == config_id


def test_client_config_relationship(integration_client):
    timestamp = int(time.time())
    config_data = {
        "name": f"Relationship Test Config {timestamp}",
        "content": {"test_key": "test_value"},
    }

    config_response = integration_client.post("/api/configs", json=config_data)
    config_id = config_response.json()["id"]

    client_data = {
        "name": f"Relationship Test Client {timestamp}",
        "config_id": config_id,
    }

    client_response = integration_client.post("/api/clients", json=client_data)
    client_id = client_response.json()["id"]

    delete_response = integration_client.delete(f"/api/configs/{config_id}")
    assert delete_response.status_code == 400

    integration_client.delete(f"/api/clients/{client_id}")

    delete_response = integration_client.delete(f"/api/configs/{config_id}")
    assert delete_response.status_code == 204


def test_config_validation(integration_client):
    timestamp = int(time.time())
    config_data = {
        "name": f"Validation Test Config {timestamp}",
        "content": {"test_key": "test_value"},
    }

    config_response = integration_client.post("/api/configs", json=config_data)
    config_id = config_response.json()["id"]

    validation_response = integration_client.post(f"/api/configs/{config_id}/validate")
    assert validation_response.status_code == 200
    assert "message" in validation_response.json()

    content_validation_response = integration_client.post(
        "/api/configs/validate",
        json={"direct_validation": "test"},
    )
    assert content_validation_response.status_code == 200
    assert "message" in content_validation_response.json()


def test_full_client_lifecycle(integration_client):
    timestamp = int(time.time())
    config_data = {
        "name": f"Lifecycle Test Config {timestamp}",
        "content": {"test_key": "test_value"},
    }

    config_response = integration_client.post("/api/configs", json=config_data)
    config_id = config_response.json()["id"]

    client_data = {
        "name": f"Lifecycle Test Client {timestamp}",
        "config_id": config_id,
    }

    client_response = integration_client.post("/api/clients", json=client_data)
    client_id = client_response.json()["id"]

    update_data = {
        "name": f"Updated Lifecycle Client {timestamp}",
        "description": "Updated description",
    }

    update_response = integration_client.put(
        f"/api/clients/{client_id}",
        json=update_data,
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == f"Updated Lifecycle Client {timestamp}"

    all_clients_response = integration_client.get("/api/clients")
    assert all_clients_response.status_code == 200
    assert len(all_clients_response.json()) >= 1

    delete_response = integration_client.delete(f"/api/clients/{client_id}")
    assert delete_response.status_code == 204

    get_response = integration_client.get(f"/api/clients/{client_id}")
    assert get_response.status_code == 404
