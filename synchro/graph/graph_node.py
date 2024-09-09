import logging
from abc import ABC, abstractmethod
from types import TracebackType
from typing import Literal, Self

from synchro.audio.frame_container import FrameContainer
from synchro.config.commons import StreamConfig

logger = logging.getLogger(__name__)


class GraphNode(ABC):
    def __init__(self, name: str) -> None:
        self._name = name
        self._logger = logger.getChild(str(self))
        self._logger.debug("Created node %s", self)

    @property
    def name(self) -> str:
        return self._name

    @abstractmethod
    def initialize_edges(
        self,
        inputs: list[StreamConfig],
        outputs: list[StreamConfig],
    ) -> None:
        pass

    @abstractmethod
    def predict_config(
        self,
        inputs: list[StreamConfig],
    ) -> StreamConfig:
        pass

    def check_inputs_count(
        self,
        inputs: list[StreamConfig],
        allowed_count: int,
    ) -> None:
        if len(inputs) != allowed_count:
            raise ValueError(
                f"Node {self} has inputs {inputs} - {allowed_count} ALLOWED",
            )

    def check_outputs_count(
        self,
        outputs: list[StreamConfig],
        allowed_count: int,
    ) -> None:
        if len(outputs) != allowed_count:
            raise ValueError(
                f"Node {self} has outputs {outputs} - {allowed_count} ALLOWED",
            )

    def check_has_inputs(self, inputs: list[StreamConfig]) -> None:
        if len(inputs) == 0:
            raise ValueError(f"Node {self} has NO inputs {inputs}")

    def check_has_outputs(self, outputs: list[StreamConfig]) -> None:
        if len(outputs) == 0:
            raise ValueError(f"Node {self} has NO outputs {outputs}")

    def __str__(self) -> str:
        return f"({self.name})"


class ContextualGraphNode(GraphNode, ABC):
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

    def __str__(self) -> str:
        return f"(-{self.name}-)"


class EmittingNodeMixin(ABC):
    @abstractmethod
    def get_data(self) -> FrameContainer:
        raise NotImplementedError


class ReceivingNodeMixin(ABC):
    @abstractmethod
    def put_data(self, data: list[FrameContainer]) -> None:
        raise NotImplementedError
