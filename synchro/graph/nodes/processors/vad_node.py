import logging

from synchro.audio.voice_activity_detector import (
    VoiceActivityDetector,
    VoiceActivityDetectorResult,
)
from synchro.config.commons import (
    MIN_BUFFER_SIZE_SEC,
    PREFERRED_BUFFER_SIZE_SEC,
    StreamConfig,
)
from synchro.config.schemas import VadNodeSchema
from synchro.graph.graph_frame_container import GraphFrameContainer
from synchro.graph.graph_node import EmittingNodeMixin, GraphNode, ReceivingNodeMixin

logger = logging.getLogger(__name__)


class VadNode(GraphNode, ReceivingNodeMixin, EmittingNodeMixin):
    def __init__(self, config: VadNodeSchema) -> None:
        super().__init__(config.name)
        self._buffer: list[bytes] = []
        self.output_config: StreamConfig | None = None
        self._to_rate = config.to_rate
        self._vad = VoiceActivityDetector(
            min_buffer_size_sec=MIN_BUFFER_SIZE_SEC,
            shrink_buffer_size_sec=PREFERRED_BUFFER_SIZE_SEC,
        )

    def put_data(self, data: list[GraphFrameContainer]) -> None:
        if len(data) != 1:
            raise ValueError(f"Expected one frame container, got {len(data)}")

        if self.output_config is None:
            self.output_config = data[0].stream_config

        self._buffer.append(data[0].frame_data)

    def get_data(self) -> GraphFrameContainer | None:
        if not self._buffer or not self.output_config:
            return None

        merged_audio = b"".join(self._buffer)

        validatable_container = GraphFrameContainer.from_config(
            self.name,
            self.output_config,
            merged_audio,
        )

        vad_result = self._vad.detect_voice(validatable_container)

        if vad_result == VoiceActivityDetectorResult.SPEECH:
            self._buffer.clear()
            return validatable_container

        if vad_result == VoiceActivityDetectorResult.NON_SPEECH:
            self._buffer.clear()

        return None
