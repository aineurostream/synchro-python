from typing import Annotated

from pydantic import BaseModel, Field


class SettingsLimitSchema(BaseModel):
    run_time_seconds: Annotated[int, Field(default=0)]


class BleuResult(BaseModel):
    node: str
    expected_text: str
    weight: Annotated[float, Field(default=1.0)]


class ExperimentsSchema(BaseModel):
    bleu: Annotated[list[BleuResult], Field(default_factory=list)]


class SettingsSchema(BaseModel):
    limits: Annotated[
        SettingsLimitSchema,
        Field(default_factory=SettingsLimitSchema),
    ]
    experiments: Annotated[
        ExperimentsSchema,
        Field(default_factory=ExperimentsSchema),
    ]
