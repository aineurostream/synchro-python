from synchroagent.database.config_registry import (
    ConfigCreate,
    ConfigUpdate,
)


def test_config_create(config_registry):
    config_create = ConfigCreate(
        name="test_config",
        content={"key": "value", "nested": {"key": "value"}},
        description="Test config description",
    )
    config = config_registry.create(config_create)

    assert config.id is not None
    assert config.name == "test_config"
    assert config.content == {"key": "value", "nested": {"key": "value"}}
    assert config.description == "Test config description"
    assert config.created_at is not None
    assert config.updated_at is not None


def test_config_get_by_id(config_registry):
    config_create = ConfigCreate(
        name="get_by_id_config",
        content={"key": "value"},
    )
    created_config = config_registry.create(config_create)

    config = config_registry.get_by_id(created_config.id)

    assert config is not None
    assert config.id == created_config.id
    assert config.name == "get_by_id_config"
    assert config.content == {"key": "value"}


def test_config_update(config_registry):
    config_create = ConfigCreate(
        name="update_config",
        content={"original": "value"},
        description="Original description",
    )
    created_config = config_registry.create(config_create)
    original_updated_at = created_config.updated_at

    config_update = ConfigUpdate(
        name="updated_config",
        content={"updated": "value"},
        description="Updated description",
    )
    updated_config = config_registry.update(created_config.id, config_update)

    assert updated_config is not None
    assert updated_config.id == created_config.id
    assert updated_config.name == "updated_config"
    assert updated_config.content == {"updated": "value"}
    assert updated_config.description == "Updated description"
    assert updated_config.created_at == created_config.created_at
    assert updated_config.updated_at != original_updated_at


def test_config_update_partial(config_registry):
    config_create = ConfigCreate(
        name="partial_update_config",
        content={"key": "value"},
        description="Original description",
    )
    created_config = config_registry.create(config_create)

    name_update = ConfigUpdate(name="name_updated_config")
    name_updated_config = config_registry.update(created_config.id, name_update)

    assert name_updated_config.name == "name_updated_config"
    assert name_updated_config.content == {"key": "value"}
    assert name_updated_config.description == "Original description"

    content_update = ConfigUpdate(content={"updated": "content"})
    content_updated_config = config_registry.update(created_config.id, content_update)

    assert content_updated_config.name == "name_updated_config"
    assert content_updated_config.content == {"updated": "content"}
    assert content_updated_config.description == "Original description"

    desc_update = ConfigUpdate(description="Updated description")
    desc_updated_config = config_registry.update(created_config.id, desc_update)

    assert desc_updated_config.name == "name_updated_config"
    assert desc_updated_config.content == {"updated": "content"}
    assert desc_updated_config.description == "Updated description"


def test_config_delete(config_registry):
    config_create = ConfigCreate(
        name="delete_config",
        content={"key": "value"},
    )
    created_config = config_registry.create(config_create)

    assert config_registry.exists(created_config.id)

    result = config_registry.delete(created_config.id)

    assert result is True
    assert not config_registry.exists(created_config.id)
    assert config_registry.get_by_id(created_config.id) is None


def test_config_get_all(config_registry):
    config_names = ["all_config_1", "all_config_2", "all_config_3"]
    for name in config_names:
        config_create = ConfigCreate(
            name=name,
            content={"key": "value"},
        )
        config_registry.create(config_create)

    configs = config_registry.get_all()

    assert len(configs) >= len(config_names)
    config_names_in_db = [config.name for config in configs]
    for name in config_names:
        assert name in config_names_in_db


def test_config_json_serialization(config_registry):
    complex_json = {
        "string": "value",
        "number": 123,
        "boolean": True,
        "null": None,
        "array": [1, 2, 3],
        "nested": {
            "key": "value",
            "array": [{"key": "value"}, {"key": "value"}],
        },
    }

    config_create = ConfigCreate(
        name="json_config",
        content=complex_json,
    )
    config = config_registry.create(config_create)

    retrieved_config = config_registry.get_by_id(config.id)
    assert retrieved_config is not None
    assert retrieved_config.content == complex_json
