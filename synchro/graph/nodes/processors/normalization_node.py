import logging
from typing import cast

from pydub import AudioSegment, effects

from synchro.audio.frame_container import FrameContainer
from synchro.config.commons import LONG_BUFFER_SIZE_SEC
from synchro.config.schemas import NormalizerNodeSchema
from synchro.graph.graph_node import EmittingNodeMixin, GraphNode, ReceivingNodeMixin

logger = logging.getLogger(__name__)


class NormalizerNode(GraphNode, ReceivingNodeMixin, EmittingNodeMixin):
    def __init__(self, config: NormalizerNodeSchema) -> None:
        super().__init__(config.name)
        self._config = config
        self._buffer: FrameContainer | None = None
        self._incoming_frames = 0

    def put_data(self, _source: str, data: FrameContainer) -> None:
        self._buffer = (
            FrameContainer.from_other(data)
            if self._buffer is None
            else self._buffer.append(data)
        )
        self._incoming_frames += data.length_frames

    def get_data(self) -> FrameContainer | None:
        if not self._buffer or self._incoming_frames == 0:
            return None
        normalized_audio = self._normalize_audio(self._buffer).get_end_frames(
            self._incoming_frames,
        )
        self._buffer = self._buffer.get_end_seconds(LONG_BUFFER_SIZE_SEC)
        self._incoming_frames = 0

        return normalized_audio

    def _normalize_audio(self, buffer: FrameContainer) -> FrameContainer:
        audio_segment = AudioSegment(
            buffer.frame_data,
            frame_rate=buffer.rate,
            sample_width=buffer.audio_format.sample_size,
            channels=1,
        )
        audio_segment = effects.normalize(audio_segment, headroom=self._config.headroom)
        return FrameContainer.from_config(
            buffer,
            cast(bytes, audio_segment.raw_data),
        )
