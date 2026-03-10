import logging

import numpy as np
import soxr

from synchro.audio.frame_container import FrameContainer
from synchro.config.commons import StreamConfig
from synchro.config.schemas import ResamplerNodeSchema
from synchro.graph.graph_node import EmittingNodeMixin, GraphNode, ReceivingNodeMixin

INT16_MAX = 32767

logger = logging.getLogger(__name__)


class ResampleNode(GraphNode, ReceivingNodeMixin, EmittingNodeMixin):
    def __init__(self, config: ResamplerNodeSchema) -> None:
        super().__init__(config.name)
        self._buffer: FrameContainer | None = None
        self._to_rate = config.to_rate

    def put_data(self, _source: str, data: FrameContainer) -> None:
        self._buffer = (
            data.clone() if self._buffer is None else self._buffer.append(data)
        )

    def get_data(self) -> FrameContainer | None:
        if not self._buffer:
            return None

        converted_payload_np = np.frombuffer(
            self._buffer.frame_data,
            dtype=self._buffer.audio_format.numpy_format,
        )
        resulting_payload = soxr.resample(
            converted_payload_np,
            self._buffer.rate,
            self._to_rate,
        )
        converted_payload = resulting_payload.tobytes()
        self._logger.debug(
            "Resampled %d bytes from %d to %d in %s",
            len(converted_payload),
            self._buffer.rate,
            self._to_rate,
            self,
        )
        self._buffer = self._buffer.to_empty()
        return FrameContainer.from_config(
            StreamConfig(rate=self._to_rate, audio_format=self._buffer.audio_format),
            converted_payload,
        )
