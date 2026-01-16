from typing import Annotated

from pydantic import BaseModel, Field


class SettingsLimitSchema(BaseModel):
    run_time_seconds: Annotated[int, Field(default=0)]


class QualityInfo(BaseModel):
    node: str
    expected_translation: str
    expected_transcription: str
    weight: Annotated[float, Field(default=1.0)]


class MetricsSchema(BaseModel):
    quality: Annotated[list[QualityInfo], Field(default_factory=list)]


class SettingsSchema(BaseModel):
    name: str
    input_interval_secs: Annotated[float, Field(default=0.3)]
    processor_interval_secs: Annotated[float, Field(default=0.016)]
    limits: Annotated[
        SettingsLimitSchema,
        Field(default_factory=SettingsLimitSchema),
    ]
    metrics: Annotated[
        MetricsSchema,
        Field(default_factory=MetricsSchema),
    ]
