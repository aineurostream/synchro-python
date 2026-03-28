from typing import Annotated, NoReturn, cast

from fastapi import APIRouter, Depends, Path, status
from pydantic import BaseModel

from synchroagent.api.deps import (
    LogRouteDeps,
    ReportRouteDeps,
    get_client_process_manager,
    get_client_registry_dep,
    get_client_run_registry_dep,
    get_log_route_deps,
    get_report_registry_dep,
    get_report_route_deps,
)
from synchroagent.api.errors import BadRequestError, NotFoundError, ServerError
from synchroagent.database.client_registry import ClientRegistry
from synchroagent.database.client_run_registry import ClientRunRegistry
from synchroagent.database.models import ClientSchema, RunStatus
from synchroagent.database.report_registry import ReportRegistry
from synchroagent.logic.client_process_manager import ClientProcessManager

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


def _raise_not_found(message: str) -> NoReturn:
    raise NotFoundError(message)


@router.get("")
async def get_clients(
    client_registry: Annotated[ClientRegistry, Depends(get_client_registry_dep)],
) -> list[ClientResponse]:
    clients = client_registry.get_all()
    return [
        cast("ClientResponse", ClientResponse.model_validate(client.model_dump()))
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
        "ClientResponse",
        ClientResponse.model_validate(created_client.model_dump()),
    )


@router.get("/{client_id}")
async def get_client(
    client_id: Annotated[int, Path(ge=1)],
    client_registry: Annotated[ClientRegistry, Depends(get_client_registry_dep)],
) -> ClientResponse:
    client = client_registry.get_by_id(client_id)
    if not client:
        msg = "Client not found"
        raise NotFoundError(msg)

    return cast("ClientResponse", ClientResponse.model_validate(client.model_dump()))


@router.put("/{client_id}")
async def update_client(
    client_id: Annotated[int, Path(ge=1)],
    client_data: ClientUpdate,
    client_registry: Annotated[ClientRegistry, Depends(get_client_registry_dep)],
) -> ClientResponse:
    existing_client = client_registry.get_by_id(client_id)
    if not existing_client:
        msg = "Client not found"
        raise NotFoundError(msg)

    updated_client = client_registry.update(client_id, client_data)

    if not updated_client:
        msg = "Failed to update client"
        raise BadRequestError(msg)

    return cast(
        "ClientResponse",
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
        msg = "Client not found"
        raise NotFoundError(msg)

    all_runs = client_run_registry.get_runs_by_client_id(client_id)
    active_runs = [r for r in all_runs if r.status == RunStatus.RUNNING]
    if active_runs:
        msg = "Cannot delete client with active runs. Stop all runs first."
        raise BadRequestError(
            msg,
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
        msg = "Client not found"
        raise NotFoundError(msg)

    runs = client_run_registry.get_runs_by_client_id(client_id)
    return [
        cast("ClientRunResponse", ClientRunResponse.model_validate(run.model_dump()))
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
        msg = "Client not found"
        raise NotFoundError(msg)

    config_id = run_data.config_id or client.config_id
    if not config_id:
        msg = (
            "No configuration specified. Provide "
            "config_id or set a default config for the client."
        )
        raise BadRequestError(
            msg,
        )

    try:
        client_run = client_process_manager.start_client(client_id, config_id)
        return cast(
            "ClientRunResponse",
            ClientRunResponse.model_validate(client_run.model_dump()),
        )
    except Exception as e:
        msg = "Failed to start client"
        raise ServerError(msg) from e


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
        msg = "Client not found"
        raise NotFoundError(msg)

    run = client_run_registry.get_by_id(run_id)
    if not run or run.client_id != client_id:
        msg = "Client run not found"
        raise NotFoundError(msg)

    return cast(
        "ClientRunResponse",
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
        msg = "Client not found"
        raise NotFoundError(msg)

    run = client_run_registry.get_by_id(run_id)
    if not run or run.client_id != client_id:
        msg = "Client run not found"
        raise NotFoundError(msg)

    if run.status != RunStatus.RUNNING:
        msg = f"Client run is not running (status: {run.status})"
        raise BadRequestError(msg)

    try:
        client_process_manager.stop_client_run(run_id)
    except Exception as e:
        msg = "Failed to stop client run"
        raise ServerError(msg) from e


@router.get("/{client_id}/runs/{run_id}/logs")
async def get_client_run_logs(
    client_id: Annotated[int, Path(ge=1)],
    run_id: Annotated[int, Path(ge=1)],
    route_deps: Annotated[LogRouteDeps, Depends(get_log_route_deps)],
) -> LogResponse:
    log_manager, log_registry, client_registry, client_run_registry = route_deps
    client = client_registry.get_by_id(client_id)
    if not client:
        msg = "Client not found"
        raise NotFoundError(msg)

    run = client_run_registry.get_by_id(run_id)
    if not run or run.client_id != client_id:
        msg = "Client run not found"
        raise NotFoundError(msg)

    if run.log_id:
        log = log_registry.get_by_id(run.log_id)
        if log:
            return cast(
                "LogResponse",
                LogResponse.model_validate(log.model_dump()),
            )

    if run.status in [RunStatus.STOPPED, RunStatus.FAILED]:
        try:
            log_id = log_manager.collect_logs(run_id)
            if log_id:
                log = log_registry.get_by_id(log_id)
                if log:
                    return cast(
                        "LogResponse",
                        LogResponse.model_validate(log.model_dump()),
                    )
        except Exception as e:
            msg = "Failed to collect logs"
            raise ServerError(msg) from e

    msg = "Logs not found for this run"
    raise NotFoundError(msg)


@router.get("/{client_id}/reports")
async def get_client_reports(
    client_id: Annotated[int, Path(ge=1)],
    report_registry: Annotated[ReportRegistry, Depends(get_report_registry_dep)],
    client_registry: Annotated[ClientRegistry, Depends(get_client_registry_dep)],
) -> list[ReportResponse]:
    client = client_registry.get_by_id(client_id)
    if not client:
        msg = "Client not found"
        raise NotFoundError(msg)

    reports = report_registry.get_reports_by_client_id(
        client_id,
    )
    return [ReportResponse.model_validate(report.model_dump()) for report in reports]


@router.get("/{client_id}/runs/{run_id}/report")
async def get_client_run_report(
    client_id: Annotated[int, Path(ge=1)],
    run_id: Annotated[int, Path(ge=1)],
    route_deps: Annotated[ReportRouteDeps, Depends(get_report_route_deps)],
) -> ReportResponse:
    report_manager, report_registry, client_registry, client_run_registry = route_deps
    client = client_registry.get_by_id(client_id)
    if not client:
        msg = "Client not found"
        raise NotFoundError(msg)

    run = client_run_registry.get_by_id(run_id)
    if not run or run.client_id != client_id:
        msg = "Client run not found"
        raise NotFoundError(msg)

    if run.report_id:
        report = report_registry.get_by_id(run.report_id)
        if report:
            return cast(
                "ReportResponse",
                ReportResponse.model_validate(report.model_dump()),
            )

    if run.status in [RunStatus.STOPPED, RunStatus.FAILED]:
        try:
            report_id = report_manager.generate_report(run_id)
            if report_id:
                report = report_registry.get_by_id(report_id)
                if report:
                    return cast(
                        "ReportResponse",
                        ReportResponse.model_validate(report.model_dump()),
                    )
        except Exception as e:
            msg = "Failed to generate report"
            raise ServerError(msg) from e

    msg = "Report not found for this run"
    raise NotFoundError(msg)


@router.post("/{client_id}/runs/{run_id}/report")
async def generate_client_run_report(
    client_id: Annotated[int, Path(ge=1)],
    run_id: Annotated[int, Path(ge=1)],
    route_deps: Annotated[ReportRouteDeps, Depends(get_report_route_deps)],
) -> ReportResponse:
    report_manager, report_registry, client_registry, client_run_registry = route_deps
    client = client_registry.get_by_id(client_id)
    if not client:
        msg = "Client not found"
        raise NotFoundError(msg)

    run = client_run_registry.get_by_id(run_id)
    if not run or run.client_id != client_id:
        msg = "Client run not found"
        raise NotFoundError(msg)

    if run.status not in [RunStatus.STOPPED, RunStatus.FAILED]:
        msg = (
            "Cannot generate report for a run that "
            f"is not finished (status: {run.status})"
        )
        raise BadRequestError(
            msg,
        )

    try:
        report_id = report_manager.generate_report(run_id)
        report = report_registry.get_by_id(report_id)

        if not report:
            msg = "Report not found"
            _raise_not_found(msg)

        return cast(
            "ReportResponse",
            ReportResponse.model_validate(report.model_dump()),
        )
    except (NotFoundError, BadRequestError):
        raise
    except Exception as e:
        msg = "Failed to generate report"
        raise ServerError(msg) from e
