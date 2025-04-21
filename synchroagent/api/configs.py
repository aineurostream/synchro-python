from typing import Annotated, Any, cast

import sounddevice as sd
from fastapi import APIRouter, Depends, Path, status
from pydantic import BaseModel

from synchroagent.api.deps import get_client_registry_dep, get_config_registry_dep
from synchroagent.api.errors import BadRequestError, NotFoundError
from synchroagent.database.client_registry import ClientRegistry
from synchroagent.database.config_registry import ConfigRegistry
from synchroagent.database.models import ConfigSchema
from synchroagent.utils import get_datetime_iso

router = APIRouter(tags=["configs"])


class ConfigCreate(BaseModel):
    name: str
    content: dict[str, Any]
    description: str | None = None


class ConfigUpdate(BaseModel):
    name: str | None = None
    content: dict[str, Any] | None = None
    description: str | None = None


class ConfigResponse(BaseModel):
    id: int
    name: str
    content: dict[str, Any]
    description: str | None = None
    created_at: str
    updated_at: str


class ValidationResponse(BaseModel):
    message: str
    config_id: int | None = None


class SoundDeviceInfo(BaseModel):
    name: str
    max_input_channels: int
    max_output_channels: int
    default_samplerate: float
    device_id: int


@router.get("")
async def get_configs(
    config_registry: Annotated[ConfigRegistry, Depends(get_config_registry_dep)],
) -> list[ConfigResponse]:
    configs = config_registry.get_all()
    return [ConfigResponse.model_validate(config.model_dump()) for config in configs]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_config(
    config_data: ConfigCreate,
    config_registry: Annotated[ConfigRegistry, Depends(get_config_registry_dep)],
) -> ConfigResponse:
    now = get_datetime_iso()
    config = ConfigSchema(
        id=0,
        name=config_data.name,
        content=config_data.content,
        description=config_data.description,
        created_at=now,
        updated_at=now,
    )

    created_config = config_registry.create(config)
    return cast(
        ConfigResponse,
        ConfigResponse.model_validate(created_config.model_dump()),
    )


@router.get("/{config_id}")
async def get_config(
    config_id: Annotated[int, Path(ge=1)],
    config_registry: Annotated[ConfigRegistry, Depends(get_config_registry_dep)],
) -> ConfigResponse:
    config = config_registry.get_by_id(config_id)
    if not config:
        raise NotFoundError("Configuration not found")

    return cast(ConfigResponse, ConfigResponse.model_validate(config.model_dump()))


@router.put("/{config_id}")
async def update_config(
    config_id: Annotated[int, Path(ge=1)],
    update_data: ConfigUpdate,
    config_registry: Annotated[ConfigRegistry, Depends(get_config_registry_dep)],
) -> ConfigResponse:
    existing_config = config_registry.get_by_id(config_id)
    if not existing_config:
        raise NotFoundError("Configuration not found")

    updated_config = config_registry.update(config_id, update_data)

    if not updated_config:
        raise BadRequestError("Failed to update configuration")

    return cast(
        ConfigResponse,
        ConfigResponse.model_validate(updated_config.model_dump()),
    )


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_config(
    config_id: Annotated[int, Path(ge=1)],
    config_registry: Annotated[ConfigRegistry, Depends(get_config_registry_dep)],
    client_registry: Annotated[ClientRegistry, Depends(get_client_registry_dep)],
) -> None:
    config = config_registry.get_by_id(config_id)
    if not config:
        raise NotFoundError("Configuration not found")

    clients_using_config = client_registry.get_clients_by_config_id(config_id)
    if clients_using_config:
        client_names = ", ".join(
            [
                client["name"] if isinstance(client, dict) else client.name
                for client in clients_using_config
            ],
        )
        raise BadRequestError(
            "Cannot delete configuration that "
            f"is being used by clients: {client_names}",
        )

    config_registry.delete(config_id)


@router.post("/{config_id}/validate", status_code=status.HTTP_200_OK)
async def validate_config(
    config_id: Annotated[int, Path(ge=1)],
    config_registry: Annotated[ConfigRegistry, Depends(get_config_registry_dep)],
) -> ValidationResponse:
    config = config_registry.get_by_id(config_id)
    if not config:
        raise NotFoundError("Configuration not found")
    return ValidationResponse(message="Configuration is valid", config_id=config_id)


@router.post("/validate", status_code=status.HTTP_200_OK)
async def validate_config_content(
    _config_data: dict[str, Any],
) -> ValidationResponse:
    return ValidationResponse(message="Configuration content is valid")


@router.get("/device/sound-devices", status_code=status.HTTP_200_OK)
async def get_sound_devices() -> list[SoundDeviceInfo]:
    devices = sd.query_devices()
    result = []

    for i, device in enumerate(devices):
        result.append(
            SoundDeviceInfo(
                name=device["name"],
                max_input_channels=device["max_input_channels"],
                max_output_channels=device["max_output_channels"],
                default_samplerate=device["default_samplerate"],
                device_id=i,
            ),
        )

    return result
