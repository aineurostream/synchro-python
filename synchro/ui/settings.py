from __future__ import annotations

import os
from typing import Any
from pathlib import Path

from pydantic import AliasChoices, BaseModel, Field


class UISettings(BaseModel):
    """UI settings resolved from env and (optionally) CLI.

    Uses Pydantic v2 field aliases to read from environment variables.
    """

    input_device: int | None = Field(
        default=None,
        validation_alias=AliasChoices("INPUT_DEVICE", "input_device"),
    )
    output_device: int | None = Field(
        default=None,
        validation_alias=AliasChoices("OUTPUT_DEVICE", "output_device"),
    )
    lang_from: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LANG_FROM", "lang_from"),
    )
    lang_to: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LANG_TO", "lang_to"),
    )
    tts_engine: str | None = Field(
        default="xtts",
        validation_alias=AliasChoices("TTS_ENGINE", "tts_engine"),
    )
    server_url: str = Field(
        default="http://127.0.0.1:8000",
        validation_alias=AliasChoices("SERVER_URL", "server_url"),
    )
    config: Path = Field(
        default="config",  # corresponds to config/config.yaml in Hydra
        validation_alias=AliasChoices("CONFIG", "config"),
    )

    def is_complete(self) -> bool:
        return (
            self.input_device is not None
            and self.output_device is not None
            and self.lang_from
            and self.lang_to
            and self.tts_engine
        )


def load_settings(cli_overrides: dict[str, Any] | None = None) -> UISettings:
    """Load settings from environment and apply CLI overrides (if provided)."""
    settings = UISettings.model_validate(os.environ)
    if cli_overrides:
        merged = {
            **settings.model_dump(), **{
                k: v 
                for k, v in cli_overrides.items() 
                if v is not None
            }
        }
        return UISettings.model_validate(merged)
    return settings
