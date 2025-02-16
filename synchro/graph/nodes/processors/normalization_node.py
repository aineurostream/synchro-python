import logging
from typing import cast

from pydub import AudioSegment, effects

from synchro.config.commons import (
    StreamConfig,
)
from synchro.config.schemas import NormalizerNodeSchema
from synchro.graph.graph_frame_container import GraphFrameContainer
from synchro.graph.graph_node import EmittingNodeMixin, GraphNode, ReceivingNodeMixin

logger = logging.getLogger(__name__)


class NormalizerNode(GraphNode, ReceivingNodeMixin, EmittingNodeMixin):
    def __init__(self, config: NormalizerNodeSchema) -> None:
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

        normalized_audio = self._normalize_audio(frame_data)

        self._buffer.clear()

        return GraphFrameContainer.from_config(
            self.name,
            self.output_config,
            normalized_audio,
        )

    def _normalize_audio(self, audio: bytes) -> bytes:
        if not self.output_config:
            raise ValueError("Output config is required")

        audio_segment = AudioSegment(
            audio,
            frame_rate=self.output_config.rate,
            sample_width=self.output_config.audio_format.sample_size,
            channels=1,
        )
        audio_segment = effects.normalize(audio_segment, headroom=self._config.headroom)

        return cast(bytes, audio_segment.raw_data)
