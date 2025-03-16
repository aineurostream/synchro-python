from synchroagent.database.client_registry import ClientCreate
from synchroagent.database.client_run_registry import (
    ClientRunCreate,
    ClientRunUpdate,
)
from synchroagent.database.models import RunStatus


def test_client_run_create(client_run_registry, test_client_item, test_config_item):
    client_run_create = ClientRunCreate(
        client_id=test_client_item.id,
        config_id=test_config_item.id,
        status=RunStatus.CREATED,
        output_dir="/tmp/test_output",
    )
    client_run = client_run_registry.create(client_run_create)
    assert client_run.id is not None
    assert client_run.client_id == test_client_item.id
    assert client_run.config_id == test_config_item.id
    assert client_run.status == RunStatus.CREATED
    assert client_run.output_dir == "/tmp/test_output"
    assert client_run.started_at is not None


def test_client_run_update(client_run_registry, test_client_item, test_config_item):
    client_run_create = ClientRunCreate(
        client_id=test_client_item.id,
        config_id=test_config_item.id,
        status=RunStatus.CREATED,
    )
    client_run = client_run_registry.create(client_run_create)

    client_run_update = ClientRunUpdate(
        pid=12345,
        status=RunStatus.RUNNING,
        output_dir="/tmp/updated_output",
    )
    updated_run = client_run_registry.update(client_run.id, client_run_update)

    assert updated_run is not None
    assert updated_run.id == client_run.id
    assert updated_run.pid == 12345
    assert updated_run.status == RunStatus.RUNNING
    assert updated_run.output_dir == "/tmp/updated_output"


def test_client_run_update_status(
    client_run_registry,
    test_client_item,
    test_config_item,
):
    client_run_create = ClientRunCreate(
        client_id=test_client_item.id,
        config_id=test_config_item.id,
        status=RunStatus.CREATED,
    )
    client_run = client_run_registry.create(client_run_create)

    updated_run = client_run_registry.update_status(client_run.id, RunStatus.RUNNING)
    assert updated_run is not None
    assert updated_run.status == RunStatus.RUNNING
    assert updated_run.finished_at is None

    failed_run = client_run_registry.update_status(client_run.id, RunStatus.FAILED)
    assert failed_run is not None
    assert failed_run.status == RunStatus.FAILED
    assert failed_run.finished_at is not None


def test_client_run_get_active_runs(
    client_run_registry,
    test_client_item,
    test_config_item,
):
    run1 = client_run_registry.create(
        ClientRunCreate.model_validate(
            {
                "client_id": test_client_item.id,
                "config_id": test_config_item.id,
                "status": RunStatus.CREATED,
            },
        ),
    )
    run2 = client_run_registry.create(
        ClientRunCreate.model_validate(
            {
                "client_id": test_client_item.id,
                "config_id": test_config_item.id,
                "status": RunStatus.FAILED,
            },
        ),
    )
    run3 = client_run_registry.create(
        ClientRunCreate.model_validate(
            {
                "client_id": test_client_item.id,
                "config_id": test_config_item.id,
                "status": RunStatus.RUNNING,
            },
        ),
    )
    client_run_registry.update_status(run1.id, RunStatus.RUNNING)
    client_run_registry.update_status(run2.id, RunStatus.FAILED)
    client_run_registry.update_status(run3.id, RunStatus.RUNNING)

    active_runs = client_run_registry.get_active_runs()

    assert len(active_runs) == 2
    active_run_ids = [run.id for run in active_runs]
    assert run1.id in active_run_ids
    assert run3.id in active_run_ids
    assert run2.id not in active_run_ids


def test_client_run_get_runs_by_client_id(
    client_run_registry,
    client_registry,
    test_config_item,
):
    client1 = client_registry.create(
        ClientCreate.model_validate(
            {
                "name": "run_client_1",
                "config_id": test_config_item.id,
            },
        ),
    )
    client2 = client_registry.create(
        ClientCreate.model_validate(
            {
                "name": "run_client_2",
                "config_id": test_config_item.id,
            },
        ),
    )

    run1 = client_run_registry.create(
        ClientRunCreate(
            client_id=client1.id,
            config_id=test_config_item.id,
            status=RunStatus.CREATED,
        ),
    )
    run2 = client_run_registry.create(
        ClientRunCreate(
            client_id=client1.id,
            config_id=test_config_item.id,
            status=RunStatus.CREATED,
        ),
    )
    run3 = client_run_registry.create(
        ClientRunCreate(
            client_id=client2.id,
            config_id=test_config_item.id,
            status=RunStatus.CREATED,
        ),
    )

    client1_runs = client_run_registry.get_runs_by_client_id(client1.id)

    assert len(client1_runs) == 2
    client1_run_ids = [run.id for run in client1_runs]
    assert run1.id in client1_run_ids
    assert run2.id in client1_run_ids
    assert run3.id not in client1_run_ids

    client2_runs = client_run_registry.get_runs_by_client_id(client2.id)

    assert len(client2_runs) == 1
    assert client2_runs[0].id == run3.id
