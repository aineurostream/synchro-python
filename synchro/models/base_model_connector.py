from abc import ABC, abstractmethod
from types import TracebackType
from typing import Literal, Self

from synchro.input_output.schemas import InputAudioStreamConfig, OutputAudioStreamConfig


class BaseModelConnector(ABC):
    def __init__(
        self,
        input_config: InputAudioStreamConfig,
        output_config: OutputAudioStreamConfig,
    ) -> None:
        self.input_config = input_config
        self.output_config = output_config

    @property
    def from_language(self) -> str:
        return self.input_config.language

    @property
    def to_language(self) -> str:
        return self.output_config.language

    @abstractmethod
    def __enter__(self) -> Self:
        raise NotImplementedError

    @abstractmethod
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> Literal[False]:
        raise NotImplementedError

    @abstractmethod
    def send(self, samples: bytes) -> None:
        raise NotImplementedError

    @abstractmethod
    def receive(self) -> bytes:
        raise NotImplementedError
