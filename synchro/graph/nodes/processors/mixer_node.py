from typing import cast

import numpy as np

from synchro.audio.frame_container import FrameContainer
from synchro.config.commons import StreamConfig, MIN_STEP_LENGTH_SECS, MIN_WORKING_STEP_LENGTH_SECS
from synchro.config.schemas import MixerNodeSchema
from synchro.graph.graph_frame_container import GraphFrameContainer
from synchro.graph.graph_node import EmittingNodeMixin, GraphNode, ReceivingNodeMixin

MIN_MIXING_LENGTH_MULT = 10


class MixerNode(GraphNode, ReceivingNodeMixin, EmittingNodeMixin):
    def __init__(self, config: MixerNodeSchema) -> None:
        super().__init__(config.name)
        self._incoming_buffer: dict[str, FrameContainer] = {}
        self._stream_config: StreamConfig | None = None
        self._buffer: FrameContainer | None = None

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
        self.check_audio_formats(inputs)
        self._stream_config = inputs[0]
        self._buffer = FrameContainer(
            audio_format=self._stream_config.audio_format,
            rate=self._stream_config.rate,
            frame_data=b"",
        )

        return inputs[0]

    def put_data(self, data: list[GraphFrameContainer]) -> None:
        if self._stream_config is None:
            raise ValueError("Stream config is not set")

        if len(data) == 0:
            return

        for frame in data:
            if frame.source not in self._incoming_buffer:
                self._incoming_buffer[frame.source] = FrameContainer(
                    audio_format=frame.audio_format,
                    rate=frame.rate,
                    frame_data=b"",
                )

            self._incoming_buffer[frame.source].append_bytes(frame.frame_data)

    def get_data(self) -> GraphFrameContainer:
        if self._buffer is None:
            raise ValueError("Buffer is not set")

        if self._stream_config is None:
            raise ValueError("Stream config is not set")

        mixed_frames = self.mix_frames()
        self._logger.debug(
            "Merging %d bytes in %s",
            len(mixed_frames),
            self.name,
        )

        self._buffer.append_bytes(mixed_frames)

        if self._stream_config is None:
            raise ValueError("Stream config is not set")

        if len(self._buffer) == 0:
            return GraphFrameContainer.from_config(
                self.name,
                self._stream_config,
            )

        returning_frame = GraphFrameContainer.from_frame_container(
            self.name,
            self._stream_config.language,
            self._buffer,
        )
        self._buffer.clear()

        return returning_frame

    def mix_frames(self) -> bytes:
        if self._stream_config is None:
            raise ValueError("Stream config is not set")

        min_length_frames = (
                MIN_WORKING_STEP_LENGTH_SECS
                * MIN_MIXING_LENGTH_MULT
                * self._stream_config.rate
        )
        selected_frame_containers = []
        for frame in self._incoming_buffer.values():
            current_frame_length = frame.length_frames()
            if current_frame_length > min_length_frames:
                selected_frame_containers.append(frame)

        if len(selected_frame_containers) == 0:
            return b""

        cut_length_frames = int(
            MIN_WORKING_STEP_LENGTH_SECS * self._stream_config.rate
        )
        audio_matrix = np.zeros(
            (
                len(selected_frame_containers),
                cut_length_frames,
            ),
            dtype=self._stream_config.audio_format.numpy_format,
        )
        for i, frame in enumerate(selected_frame_containers):
            audio_matrix[i] = np.frombuffer(
                frame.frames_to_bytes(cut_length_frames),
                dtype=self._stream_config.audio_format.numpy_format,
            )
            frame.shrink(cut_length_frames)

        return cast(
            bytes,
            np.mean(audio_matrix, axis=0)
            .astype(self._stream_config.audio_format.numpy_format)
            .tobytes()
        )
