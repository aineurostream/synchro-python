import logging

from synchro.config.commons import (
    StreamConfig,
)
from synchro.config.schemas import (
    DenoiserNodeSchema,
)
from synchro.graph.graph_frame_container import GraphFrameContainer
from synchro.graph.graph_node import EmittingNodeMixin, GraphNode, ReceivingNodeMixin

logger = logging.getLogger(__name__)


class DenoiserNode(GraphNode, ReceivingNodeMixin, EmittingNodeMixin):
    def __init__(self, config: DenoiserNodeSchema) -> None:
        super().__init__(config.name)
        self._buffer: list[bytes] = []
        self._config = config
        self.output_config: StreamConfig | None = None

    def put_data(self, data: list[GraphFrameContainer]) -> None:
        if len(data) != 1:
            raise ValueError(f"Expected one frame container, got {len(data)}")

        if self.output_config is None:
            self.output_config = data[0].stream_config

        self._buffer.append(data[0].frame_data)

    def get_data(self) -> GraphFrameContainer | None:
        if not self._buffer or not self.output_config:
            return None

        frame_data = b"".join(self._buffer)

        denoised_audio = self._denoise_audio(frame_data)

        return GraphFrameContainer.from_config(
            self.name,
            self.output_config,
            denoised_audio,
        )

    def _denoise_audio(self, audio: bytes) -> bytes:
        raise NotImplementedError("Denoising is not implemented yet")
