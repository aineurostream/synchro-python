import logging

import numpy as np
import soxr

from synchro.config.commons import StreamConfig
from synchro.config.schemas import ResamplerNodeSchema
from synchro.graph.graph_frame_container import GraphFrameContainer
from synchro.graph.graph_node import EmittingNodeMixin, GraphNode, ReceivingNodeMixin

INT16_MAX = 32767

logger = logging.getLogger(__name__)


class ResampleNode(GraphNode, ReceivingNodeMixin, EmittingNodeMixin):
    def __init__(self, config: ResamplerNodeSchema) -> None:
        super().__init__(config.name)
        self._buffer: list[GraphFrameContainer] = []
        self.output_config: StreamConfig | None = None
        self._to_rate = config.to_rate

    def put_data(self, data: list[GraphFrameContainer]) -> None:
        if len(data) != 1:
            raise ValueError(f"Expected one frame container, got {len(data)}")

        if self.output_config is None:
            self.output_config = StreamConfig(
                language=data[0].language,
                audio_format=data[0].audio_format,
                rate=self._to_rate,
            )

        self._buffer.append(data[0])

    def get_data(self) -> GraphFrameContainer | None:
        if not self._buffer or not self.output_config:
            return None

        initial_payload = b"".join([frame.frame_data for frame in self._buffer])
        from_rate = self._buffer[0].rate
        self._buffer.clear()

        if len(initial_payload) == 0:
            return None

        converted_payload_np = np.frombuffer(
            initial_payload,
            dtype=self.output_config.audio_format.numpy_format,
        )
        resulting_payload = soxr.resample(
            converted_payload_np,
            from_rate,
            self._to_rate,
        )
        converted_payload = resulting_payload.tobytes()
        self._logger.debug(
            "Resampled %d bytes from %d to %d in %s",
            len(converted_payload),
            from_rate,
            self._to_rate,
            self,
        )

        return GraphFrameContainer.from_config(
            self.name,
            self.output_config,
            converted_payload,
        )
