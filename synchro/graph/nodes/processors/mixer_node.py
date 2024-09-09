from typing import cast

import numpy as np

from synchro.audio.frame_container import FrameContainer
from synchro.config.commons import StreamConfig
from synchro.config.schemas import MixerNodeSchema
from synchro.graph.graph_node import EmittingNodeMixin, GraphNode, ReceivingNodeMixin


class MixerNode(GraphNode, ReceivingNodeMixin, EmittingNodeMixin):
    def __init__(self, config: MixerNodeSchema) -> None:
        super().__init__(config.name)
        self._buffer: list[FrameContainer] = []
        self._stream_config: StreamConfig | None = None

    def initialize_edges(
        self,
        inputs: list[StreamConfig],
        outputs: list[StreamConfig],
    ) -> None:
        self.check_has_inputs(inputs)
        self.check_has_outputs(outputs)

    def predict_config(
        self,
        inputs: list[StreamConfig],
    ) -> StreamConfig:
        self.check_has_inputs(inputs)
        self._stream_config = inputs[0]
        return inputs[0]

    def put_data(self, data: list[FrameContainer]) -> None:
        if self._stream_config is None:
            raise ValueError("Stream config is not set")

        if len(data) == 0:
            return

        mixed_frames = self.mix_frames(data)
        self._logger.debug(
            "Merging %d bytes in %s",
            len(mixed_frames),
            self.name,
        )
        self._buffer.append(
            FrameContainer.from_config(
                self._stream_config,
                mixed_frames,
            ),
        )

    def get_data(self) -> FrameContainer:
        if self._stream_config is None:
            raise ValueError("Stream config is not set")

        if len(self._buffer) == 0:
            return FrameContainer.from_config(self._stream_config)
        return self._buffer.pop(0)

    @staticmethod
    def mix_frames(frames: list[FrameContainer]) -> bytes:
        min_length_frames = 0
        for frame in frames:
            current_frame_length = len(frame)
            if min_length_frames > current_frame_length or min_length_frames == 0:
                min_length_frames = current_frame_length

        if min_length_frames == 0:
            return b""

        audio_matrix = np.zeros((len(frames), min_length_frames), dtype=np.int16)
        for i, frame in enumerate(frames):
            audio_matrix[i] = np.frombuffer(
                frame.frame_data,
                dtype=np.int16,
            )[:min_length_frames]

        return cast(bytes, np.mean(audio_matrix, axis=0).astype(np.int16).tobytes())
