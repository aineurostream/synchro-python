import logging
from collections.abc import Mapping
from enum import Enum
from typing import cast

logger = logging.getLogger(__name__)


class DeviceMode(Enum):
    INACTIVE = "inactive"
    INPUT = "input"
    OUTPUT = "output"
    INPUT_OUTPUT = "input_output"


class AudioDevice:
    """
    Represents an audio device with information about its input
    and output capabilities.
    """

    def __init__(
        self,
        device_index: int,
        device_info: Mapping[str, str | int | float],
    ) -> None:
        self.device_index: int = device_index
        self.name = device_info["name"]
        self.input_channels: int = cast(int, device_info["maxInputChannels"])
        self.output_channels: int = cast(int, device_info["maxOutputChannels"])

    @property
    def mode(self) -> DeviceMode:
        if self.input_channels > 0 and self.output_channels > 0:
            return DeviceMode.INPUT_OUTPUT

        if self.input_channels > 0:
            return DeviceMode.INPUT

        if self.output_channels > 0:
            return DeviceMode.OUTPUT

        return DeviceMode.INACTIVE

    def __str__(self) -> str:
        return (
            f"{self.device_index}: {self.name} "
            f"(in: {self.input_channels}, out: {self.output_channels})"
        )
