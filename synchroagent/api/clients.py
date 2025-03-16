from typing import Annotated, cast

from fastapi import APIRouter, Depends, Path, status
from pydantic import BaseModel

from synchroagent.api.deps import (
    get_client_process_manager,
    get_client_registry_dep,
    get_client_run_registry_dep,
    get_log_manager,
    get_log_registry_dep,
    get_report_manager,
    get_report_registry_dep,
)
from synchroagent.api.errors import BadRequestError, NotFoundError, ServerError
from synchroagent.database.client_registry import ClientRegistry
from synchroagent.database.client_run_registry import ClientRunRegistry
from synchroagent.database.log_registry import LogRegistry
from synchroagent.database.models import ClientSchema, RunStatus
from synchroagent.database.report_registry import ReportRegistry
from synchroagent.logic.client_process_manager import ClientProcessManager
from synchroagent.logic.log_manager import LogManager
from synchroagent.logic.report_manager import ReportManager

router = APIRouter(tags=["clients"])


class ClientCreate(BaseModel):
    name: str
    description: str | None = None
    config_id: int | None = None


class ClientUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    config_id: int | None = None


class ClientResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    config_id: int | None = None


class ClientRunCreate(BaseModel):
    config_id: int | None = None


class ClientRunResponse(BaseModel):
    id: int
    client_id: int
    config_id: int
    pid: int | None = None
    status: RunStatus
    output_dir: str | None = None
    report_id: int | None = None
    log_id: int | None = None
    exit_code: int | None = None
    started_at: str | None = None
    finished_at: str | None = None


class LogResponse(BaseModel):
    id: int
    client_run_id: int
    content: str
    log_type: str
    created_at: str | None = None


class ReportResponse(BaseModel):
    id: int
    client_id: int
    content: str | None = None
    size: int | None = None
    generated_at: str | None = None


@router.get("")
async def get_clients(
    client_registry: Annotated[ClientRegistry, Depends(get_client_registry_dep)],
) -> list[ClientResponse]:
    clients = client_registry.get_all()
    return [
        cast(ClientResponse, ClientResponse.model_validate(client.model_dump()))
        for client in clients
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_client(
    client_data: ClientCreate,
    client_registry: Annotated[ClientRegistry, Depends(get_client_registry_dep)],
) -> ClientResponse:
    client = ClientSchema(
        id=0,
        name=client_data.name,
        description=client_data.description,
        config_id=client_data.config_id,
    )

    created_client = client_registry.create(client)
    return cast(
        ClientResponse,
        ClientResponse.model_validate(created_client.model_dump()),
    )


@router.get("/{client_id}")
async def get_client(
    client_id: Annotated[int, Path(ge=1)],
    client_registry: Annotated[ClientRegistry, Depends(get_client_registry_dep)],
) -> ClientResponse:
    client = client_registry.get_by_id(client_id)
    if not client:
        raise NotFoundError("Client not found")

    return cast(ClientResponse, ClientResponse.model_validate(client.model_dump()))


@router.put("/{client_id}")
async def update_client(
    client_id: Annotated[int, Path(ge=1)],
    client_data: ClientUpdate,
    client_registry: Annotated[ClientRegistry, Depends(get_client_registry_dep)],
) -> ClientResponse:
    existing_client = client_registry.get_by_id(client_id)
    if not existing_client:
        raise NotFoundError("Client not found")

    update_data = client_data.model_dump(exclude_unset=True)
    updated_client = client_registry.update(client_id, update_data)

    if not updated_client:
        raise BadRequestError("Failed to update client")

    return cast(
        ClientResponse,
        ClientResponse.model_validate(updated_client.model_dump()),
    )


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client(
    client_id: Annotated[int, Path(ge=1)],
    client_registry: Annotated[ClientRegistry, Depends(get_client_registry_dep)],
    client_run_registry: Annotated[
        ClientRunRegistry,
        Depends(get_client_run_registry_dep),
    ],
) -> None:
    client = client_registry.get_by_id(client_id)
    if not client:
        raise NotFoundError("Client not found")

    active_runs = client_run_registry.get_runs_by_client_id(client_id)
    if active_runs:
        raise BadRequestError(
            "Cannot delete client with active runs. Remove all runs first.",
        )

    client_registry.delete(client_id)


@router.get("/{client_id}/runs")
async def get_client_runs(
    client_id: Annotated[int, Path(ge=1)],
    client_run_registry: Annotated[
        ClientRunRegistry,
        Depends(get_client_run_registry_dep),
    ],
    client_registry: Annotated[ClientRegistry, Depends(get_client_registry_dep)],
) -> list[ClientRunResponse]:
    client = client_registry.get_by_id(client_id)
    if not client:
        raise NotFoundError("Client not found")

    runs = client_run_registry.get_runs_by_client_id(client_id)
    return [
        cast(ClientRunResponse, ClientRunResponse.model_validate(run.model_dump()))
        for run in runs
    ]


@router.post(
    "/{client_id}/runs",
    status_code=status.HTTP_201_CREATED,
)
async def start_client_run(
    client_id: Annotated[int, Path(ge=1)],
    run_data: ClientRunCreate,
    client_process_manager: Annotated[
        ClientProcessManager,
        Depends(get_client_process_manager),
    ],
    client_registry: Annotated[ClientRegistry, Depends(get_client_registry_dep)],
) -> ClientRunResponse:
    client = client_registry.get_by_id(client_id)
    if not client:
        raise NotFoundError("Client not found")

    config_id = run_data.config_id or client.config_id
    if not config_id:
        raise BadRequestError(
            "No configuration specified. Provide "
            "config_id or set a default config for the client.",
        )

    try:
        client_run = client_process_manager.start_client(client_id, config_id)
        return cast(
            ClientRunResponse,
            ClientRunResponse.model_validate(client_run.model_dump()),
        )
    except Exception as e:
        raise ServerError("Failed to start client") from e


@router.get("/{client_id}/runs/{run_id}")
async def get_client_run(
    client_id: Annotated[int, Path(ge=1)],
    run_id: Annotated[int, Path(ge=1)],
    client_run_registry: Annotated[
        ClientRunRegistry,
        Depends(get_client_run_registry_dep),
    ],
    client_registry: Annotated[ClientRegistry, Depends(get_client_registry_dep)],
) -> ClientRunResponse:
    client = client_registry.get_by_id(client_id)
    if not client:
        raise NotFoundError("Client not found")

    run = client_run_registry.get_by_id(run_id)
    if not run or run.client_id != client_id:
        raise NotFoundError("Client run not found")

    return cast(
        ClientRunResponse,
        ClientRunResponse.model_validate(run.model_dump()),
    )


@router.delete("/{client_id}/runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def stop_client_run(
    client_id: Annotated[int, Path(ge=1)],
    run_id: Annotated[int, Path(ge=1)],
    client_process_manager: Annotated[
        ClientProcessManager,
        Depends(get_client_process_manager),
    ],
    client_registry: Annotated[ClientRegistry, Depends(get_client_registry_dep)],
    client_run_registry: Annotated[
        ClientRunRegistry,
        Depends(get_client_run_registry_dep),
    ],
) -> None:
    client = client_registry.get_by_id(client_id)
    if not client:
        raise NotFoundError("Client not found")

    run = client_run_registry.get_by_id(run_id)
    if not run or run.client_id != client_id:
        raise NotFoundError("Client run not found")

    if run.status != RunStatus.RUNNING:
        raise BadRequestError(f"Client run is not running (status: {run.status})")

    try:
        client_process_manager.stop_client_run(run_id)
    except Exception as e:
        raise ServerError("Failed to stop client run") from e


@router.get("/{client_id}/runs/{run_id}/logs")
async def get_client_run_logs(
    client_id: Annotated[int, Path(ge=1)],
    run_id: Annotated[int, Path(ge=1)],
    log_manager: Annotated[LogManager, Depends(get_log_manager)],
    log_registry: Annotated[LogRegistry, Depends(get_log_registry_dep)],
    client_registry: Annotated[ClientRegistry, Depends(get_client_registry_dep)],
    client_run_registry: Annotated[
        ClientRunRegistry,
        Depends(get_client_run_registry_dep),
    ],
) -> LogResponse:
    client = client_registry.get_by_id(client_id)
    if not client:
        raise NotFoundError("Client not found")

    run = client_run_registry.get_by_id(run_id)
    if not run or run.client_id != client_id:
        raise NotFoundError("Client run not found")

    if run.log_id:
        log = log_registry.get_by_id(run.log_id)
        if log:
            return cast(
                LogResponse,
                LogResponse.model_validate(log.model_dump()),
            )

    if run.status in [RunStatus.STOPPED, RunStatus.FAILED]:
        try:
            log_id = log_manager.collect_logs(run_id)
            if log_id:
                log = log_registry.get_by_id(log_id)
                if log:
                    return cast(
                        LogResponse,
                        LogResponse.model_validate(log.model_dump()),
                    )
        except Exception as e:
            raise ServerError("Failed to collect logs") from e

    raise NotFoundError("Logs not found for this run")


@router.get("/{client_id}/reports")
async def get_client_reports(
    client_id: Annotated[int, Path(ge=1)],
    report_registry: Annotated[ReportRegistry, Depends(get_report_registry_dep)],
    client_registry: Annotated[ClientRegistry, Depends(get_client_registry_dep)],
) -> list[ReportResponse]:
    client = client_registry.get_by_id(client_id)
    if not client:
        raise NotFoundError("Client not found")

    reports = report_registry.get_reports_by_client_id(
        client_id,
    )
    return [ReportResponse.model_validate(report.model_dump()) for report in reports]


@router.get("/{client_id}/runs/{run_id}/report")
async def get_client_run_report(
    client_id: Annotated[int, Path(ge=1)],
    run_id: Annotated[int, Path(ge=1)],
    report_manager: Annotated[ReportManager, Depends(get_report_manager)],
    report_registry: Annotated[ReportRegistry, Depends(get_report_registry_dep)],
    client_registry: Annotated[ClientRegistry, Depends(get_client_registry_dep)],
    client_run_registry: Annotated[
        ClientRunRegistry,
        Depends(get_client_run_registry_dep),
    ],
) -> ReportResponse:
    client = client_registry.get_by_id(client_id)
    if not client:
        raise NotFoundError("Client not found")

    run = client_run_registry.get_by_id(run_id)
    if not run or run.client_id != client_id:
        raise NotFoundError("Client run not found")

    if run.report_id:
        report = report_registry.get_by_id(run.report_id)
        if report:
            return cast(
                ReportResponse,
                ReportResponse.model_validate(report.model_dump()),
            )

    if run.status in [RunStatus.STOPPED, RunStatus.FAILED]:
        try:
            report_id = report_manager.generate_report(run_id)
            if report_id:
                report = report_registry.get_by_id(report_id)
                if report:
                    return cast(
                        ReportResponse,
                        ReportResponse.model_validate(report.model_dump()),
                    )
        except Exception as e:
            raise ServerError("Failed to generate report") from e

    raise NotFoundError("Report not found for this run")


@router.post("/{client_id}/runs/{run_id}/report")
async def generate_client_run_report(
    client_id: Annotated[int, Path(ge=1)],
    run_id: Annotated[int, Path(ge=1)],
    report_manager: Annotated[ReportManager, Depends(get_report_manager)],
    report_registry: Annotated[ReportRegistry, Depends(get_report_registry_dep)],
    client_registry: Annotated[ClientRegistry, Depends(get_client_registry_dep)],
    client_run_registry: Annotated[
        ClientRunRegistry,
        Depends(get_client_run_registry_dep),
    ],
) -> ReportResponse:
    client = client_registry.get_by_id(client_id)
    if not client:
        raise NotFoundError("Client not found")

    run = client_run_registry.get_by_id(run_id)
    if not run or run.client_id != client_id:
        raise NotFoundError("Client run not found")

    if run.status not in [RunStatus.STOPPED, RunStatus.FAILED]:
        raise BadRequestError(
            "Cannot generate report for a run that "
            f"is not finished (status: {run.status})",
        )

    try:
        report_id = report_manager.generate_report(run_id)
        report = report_registry.get_by_id(report_id)

        if not report:
            raise NotFoundError("Report not found")  # noqa: TRY301

        return cast(ReportResponse, ReportResponse.model_validate(report.model_dump()))
    except Exception as e:
        raise ServerError("Failed to generate report") from e
