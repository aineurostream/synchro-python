import logging

from synchro.audio.frame_container import FrameContainer
from synchro.config.schemas import (
    DenoiserNodeSchema,
)
from synchro.graph.graph_node import EmittingNodeMixin, GraphNode, ReceivingNodeMixin

logger = logging.getLogger(__name__)


class DenoiserNode(GraphNode, ReceivingNodeMixin, EmittingNodeMixin):
    def __init__(self, config: DenoiserNodeSchema) -> None:
        super().__init__(config.name)
        self._config = config
        self._buffer: FrameContainer | None = None

    def put_data(self, _source: str, data: FrameContainer) -> None:
        self._buffer = (
            data.clone() if self._buffer is None else self._buffer.append(data)
        )

    def get_data(self) -> FrameContainer | None:
        if not self._buffer:
            return None
        denoised_audio = self._denoise_audio(self._buffer)
        self._buffer = self._buffer.to_empty()
        return denoised_audio

    def _denoise_audio(self, audio: FrameContainer) -> FrameContainer:
        raise NotImplementedError("Denoising is not implemented yet")
