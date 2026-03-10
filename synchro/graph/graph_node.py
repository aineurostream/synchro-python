import logging
from abc import ABC, abstractmethod
from types import TracebackType
from typing import Literal, Self

from synchro.audio.frame_container import FrameContainer

logger = logging.getLogger(__name__)


class GraphNode(ABC):  # noqa: B024
    def __init__(self, name: str) -> None:
        self._name = name
        self._logger = logger.getChild(str(self))
        self._logger.debug("Created node %s", self)

    @property
    def name(self) -> str:
        return self._name

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> Literal[False]:
        return False

    def __str__(self) -> str:
        return f"({self.name})"


class EmittingNodeMixin(ABC):
    @abstractmethod
    def get_data(self) -> FrameContainer | None:
        raise NotImplementedError


class ReceivingNodeMixin(ABC):
    @abstractmethod
    def put_data(self, source: str, data: FrameContainer) -> None:
        raise NotImplementedError
