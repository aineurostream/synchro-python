from abc import ABC, abstractmethod
from types import TracebackType
from typing import Literal, Self

from synchro.input_output.schemas import InputAudioStreamConfig, OutputAudioStreamConfig


class BaseModelConnector(ABC):
    def __init__(
        self,
        source_id: str,
        input_config: InputAudioStreamConfig,
        output_config: OutputAudioStreamConfig,
    ) -> None:
        self._source_id = source_id
        self._input_config = input_config
        self._output_config = output_config

    @property
    def base_id(self) -> str:
        return f"{self.source_id}/{self.from_language}->{self.to_language}"

    @property
    def source_id(self) -> str:
        return self._source_id

    @property
    def input_rate(self) -> int:
        return self._input_config.rate

    @property
    def from_language(self) -> str:
        return self._input_config.language

    @property
    def to_language(self) -> str:
        return self._output_config.language

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

    @abstractmethod
    def is_active(self) -> bool:
        raise NotImplementedError

    def __str__(self) -> str:
        return f"[{self.base_id} (active: {self.is_active()})]"
