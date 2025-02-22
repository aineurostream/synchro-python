import logging

from synchro.audio.frame_container import FrameContainer
from synchro.audio.voice_activity_detector import (
    VoiceActivityDetector,
    VoiceActivityDetectorResult,
)
from synchro.config.commons import (
    MEDIUM_BUFFER_SIZE_SEC,
)
from synchro.config.schemas import VadNodeSchema
from synchro.graph.graph_node import EmittingNodeMixin, GraphNode, ReceivingNodeMixin

logger = logging.getLogger(__name__)


class VadNode(GraphNode, ReceivingNodeMixin, EmittingNodeMixin):
    def __init__(self, config: VadNodeSchema) -> None:
        super().__init__(config.name)
        self._threshold = config.threshold
        self._buffer: FrameContainer | None = None
        self._vad: VoiceActivityDetector | None = None

    def put_data(self, _source: str, data: FrameContainer) -> None:
        self._buffer = (
            data.clone() if self._buffer is None else self._buffer.append(data)
        )

    def get_data(self) -> FrameContainer | None:
        if not self._buffer:
            return None

        if self._vad is None:
            self._vad = VoiceActivityDetector(
                self._buffer.get_config(),
                buffer_size_sec=MEDIUM_BUFFER_SIZE_SEC,
                threshold=self._threshold,
            )
        vad_result = self._vad.detect_voice(self._buffer)
        if vad_result == VoiceActivityDetectorResult.SPEECH:
            to_return = self._buffer
            self._buffer = self._buffer.to_empty()
            return to_return

        if vad_result == VoiceActivityDetectorResult.NON_SPEECH:
            self._buffer = self._buffer.to_empty()

        return None
