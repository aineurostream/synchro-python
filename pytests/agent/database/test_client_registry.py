from synchroagent.database.client_registry import (
    ClientCreate,
    ClientUpdate,
)
from synchroagent.database.config_registry import ConfigCreate


def test_client_create(client_registry, test_config_item):
    client_create = ClientCreate(
        name="test_client",
        config_id=test_config_item.id,
        description="Test client description",
    )
    client = client_registry.create(client_create)

    assert client.id is not None
    assert client.name == "test_client"
    assert client.config_id == test_config_item.id
    assert client.description == "Test client description"


def test_client_get_by_id(client_registry, test_config_item):
    client_create = ClientCreate(
        name="get_by_id_client",
        config_id=test_config_item.id,
    )
    created_client = client_registry.create(client_create)

    client = client_registry.get_by_id(created_client.id)

    assert client is not None
    assert client.id == created_client.id
    assert client.name == "get_by_id_client"
    assert client.config_id == test_config_item.id


def test_client_update(client_registry, test_config_item):
    client_create = ClientCreate(
        name="update_client",
        config_id=test_config_item.id,
        description="Original description",
    )
    created_client = client_registry.create(client_create)

    client_update = ClientUpdate(
        name="updated_client",
        description="Updated description",
    )
    updated_client = client_registry.update(created_client.id, client_update)

    assert updated_client is not None
    assert updated_client.id == created_client.id
    assert updated_client.name == "updated_client"
    assert updated_client.description == "Updated description"
    assert updated_client.config_id == test_config_item.id


def test_client_delete(client_registry, test_config_item):
    client_create = ClientCreate(
        name="delete_client",
        config_id=test_config_item.id,
    )
    created_client = client_registry.create(client_create)

    assert client_registry.exists(created_client.id)

    result = client_registry.delete(created_client.id)

    assert result is True
    assert not client_registry.exists(created_client.id)
    assert client_registry.get_by_id(created_client.id) is None


def test_client_get_all(client_registry, test_config_item):
    client_names = ["all_client_1", "all_client_2", "all_client_3"]
    for name in client_names:
        client_create = ClientCreate(
            name=name,
            config_id=test_config_item.id,
        )
        client_registry.create(client_create)

    clients = client_registry.get_all()

    assert len(clients) >= len(client_names)
    client_names_in_db = [client.name for client in clients]
    for name in client_names:
        assert name in client_names_in_db


def test_client_filter(client_registry, config_registry, test_config_item):
    config2 = config_registry.create(
        ConfigCreate(name="filter_config", content={"key": "value"}),
    )

    client_registry.create(
        ClientCreate(name="filter_client_1", config_id=test_config_item.id),
    )
    client_registry.create(ClientCreate(name="filter_client_2", config_id=config2.id))
    client_registry.create(ClientCreate(name="filter_client_3", config_id=config2.id))

    filtered_clients = client_registry.get_clients_by_config_id(config2.id)

    assert len(filtered_clients) == 2
    client_names = [client.name for client in filtered_clients]
    assert "filter_client_2" in client_names
    assert "filter_client_3" in client_names
    assert "filter_client_1" not in client_names
