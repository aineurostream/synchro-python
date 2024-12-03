import time
from dataclasses import dataclass
from typing import cast

import numpy as np

from synchro.audio.frame_container import FrameContainer
from synchro.config.commons import (
    MIN_WORKING_STEP_LENGTH_SECS,
    StreamConfig,
)
from synchro.config.schemas import MixerNodeSchema
from synchro.graph.graph_frame_container import GraphFrameContainer
from synchro.graph.graph_node import EmittingNodeMixin, GraphNode, ReceivingNodeMixin, logger

MAX_MIXING_LENGTH_MULT = 2
MIN_MIXING_LENGTH_MULT = 1


@dataclass
class InnerFrameHolder:
    frame: FrameContainer
    streaming: bool = False


class MixerNode(GraphNode, ReceivingNodeMixin, EmittingNodeMixin):
    def __init__(self, config: MixerNodeSchema) -> None:
        super().__init__(config.name)
        self._incoming_buffer: dict[str, InnerFrameHolder] = {}
        self._stream_config: StreamConfig | None = None
        self._buffer: FrameContainer | None = None
        self._inputs_count = 1
        self._last_update_time = 0

    def put_data(self, data: list[GraphFrameContainer]) -> None:
        if self._stream_config is None:
            self._stream_config = StreamConfig(
                language=data[0].language,
                audio_format=data[0].audio_format,
                rate=data[0].rate,
            )
            self._buffer = FrameContainer(
                audio_format=self._stream_config.audio_format,
                rate=self._stream_config.rate,
                frame_data=b"",
            )

        if len(data) == 0:
            return

        for frame in data:
            if frame.source not in self._incoming_buffer:
                self._incoming_buffer[frame.source] = InnerFrameHolder(
                    FrameContainer(
                        audio_format=frame.audio_format,
                        rate=frame.rate,
                        frame_data=b"",
                    ),
                )

            self._incoming_buffer[frame.source].frame.append_bytes(frame.frame_data)

    def get_data(self) -> GraphFrameContainer | None:
        if self._buffer is None or self._stream_config is None:
            return None

        mixed_frames = self.mix_frames()
        if len(mixed_frames) == 0:
            return None

        self._logger.debug(
            "Merging %d bytes in %s",
            len(mixed_frames),
            self.name,
        )

        self._buffer.append_bytes(mixed_frames)

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
        if self._last_update_time == 0:
            self._last_update_time = time.time()

        stream_start_frames = int(
            MIN_WORKING_STEP_LENGTH_SECS
            * MAX_MIXING_LENGTH_MULT
            * self._stream_config.rate,
        )

        stream_end_frames = int(
            MIN_WORKING_STEP_LENGTH_SECS
            * MIN_MIXING_LENGTH_MULT
            * self._stream_config.rate,
        )

        batch_length_frames = int(
            MIN_WORKING_STEP_LENGTH_SECS * self._stream_config.rate,
        )

        current_time = time.time()
        delta = current_time - self._last_update_time
        sample_size = self._stream_config.audio_format.sample_size
        for source, incoming_frame in self._incoming_buffer.items():
            incoming_length = incoming_frame.frame.length_frames()
            if incoming_length < stream_start_frames and not incoming_frame.streaming:
                delta_bytes = b"\00" * int(delta * self._stream_config.rate) * sample_size
                incoming_frame.frame.append_bytes(
                    delta_bytes
                )
        self._last_update_time = current_time

        for incoming_frame in self._incoming_buffer.values():
            current_frame_length = incoming_frame.frame.length_frames()
            if current_frame_length > stream_start_frames:
                incoming_frame.streaming = True
            elif current_frame_length < stream_end_frames:
                incoming_frame.streaming = False

        selected_frame_containers = [
            incoming_frame.frame
            for incoming_frame in self._incoming_buffer.values()
            if incoming_frame.streaming
        ]

        if len(selected_frame_containers) == 0:
            return b""

        audio_matrix = np.zeros(
            (
                len(selected_frame_containers),
                batch_length_frames,
            ),
            dtype=self._stream_config.audio_format.numpy_format,
        )
        for i, selected_frame in enumerate(selected_frame_containers):
            audio_matrix[i] = np.frombuffer(
                selected_frame.frames_to_bytes(batch_length_frames),
                dtype=self._stream_config.audio_format.numpy_format,
            )
            selected_frame.shrink_first_frames(batch_length_frames)

        audio_matrix = np.divide(audio_matrix, self._inputs_count)
        audio_matrix = np.sum(audio_matrix, axis=0)

        return cast(
            bytes,
            audio_matrix.astype(
                self._stream_config.audio_format.numpy_format,
            ).tobytes(),
        )
