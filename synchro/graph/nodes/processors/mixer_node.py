import time
from typing import cast

import numpy as np
from pydantic import BaseModel

from synchro.audio.frame_container import FrameContainer
from synchro.config.schemas import MixerNodeSchema
from synchro.graph.graph_node import (
    EmittingNodeMixin,
    GraphNode,
    ReceivingNodeMixin,
)

MAX_MIXING_LENGTH_MULT = 3.0
MIN_MIXING_LENGTH_MULT = 1.0


class InnerFrameHolder(BaseModel):
    frame: FrameContainer
    streaming: bool = False


class MixerNode(GraphNode, ReceivingNodeMixin, EmittingNodeMixin):
    def __init__(self, config: MixerNodeSchema) -> None:
        super().__init__(config.name)
        self._incoming_buffers: dict[str, InnerFrameHolder] = {}
        self._output_buffer: FrameContainer | None = None
        self._inputs_count = 0
        self._last_update_time = 0.0
        self._config = config

    def put_data(self, source: str, data: FrameContainer) -> None:
        if self._output_buffer is None:
            self._output_buffer = FrameContainer(
                audio_format=data.audio_format,
                rate=data.rate,
                frame_data=b"",
            )
        if not data:
            return
        if source not in self._incoming_buffers:
            self._incoming_buffers[source] = InnerFrameHolder(frame=data)

        self._inputs_count = len(self._incoming_buffers)
        self._incoming_buffers[source].frame.append_inp(data)

    def get_data(self) -> FrameContainer | None:
        if self._output_buffer is None:
            return None
        mixed_frames = self.mix_frames()
        if len(mixed_frames) == 0:
            return None
        self._logger.debug(
            "Merging %d bytes in %s",
            len(mixed_frames),
            self.name,
        )
        self._output_buffer.append_bytes_inp(mixed_frames)
        if not self._output_buffer:
            return None
        returning_frame = self._output_buffer
        self._output_buffer = self._output_buffer.to_empty()
        return returning_frame

    def mix_frames(self) -> bytes:  # noqa: C901
        if self._output_buffer is None:
            raise ValueError("Config is not set")
        if self._last_update_time == 0.0:
            self._last_update_time = time.time()
        if self._inputs_count == 0:
            return b""

        stream_start_frames = int(
            self._config.min_working_step_length_secs
            * MAX_MIXING_LENGTH_MULT
            * self._output_buffer.rate,
        )

        stream_end_frames = int(
            self._config.min_working_step_length_secs
            * MIN_MIXING_LENGTH_MULT
            * self._output_buffer.rate,
        )

        batch_length_frames = int(
            self._config.min_working_step_length_secs * self._output_buffer.rate,
        )

        current_time = time.time()
        delta = current_time - self._last_update_time
        sample_size = self._output_buffer.audio_format.sample_size

        for incoming_frame in self._incoming_buffers.values():
            incoming_length = incoming_frame.frame.length_frames
            if incoming_length < stream_start_frames and not incoming_frame.streaming:
                delta_bytes = (
                    b"\00" * int(delta * self._output_buffer.rate) * sample_size
                )
                incoming_frame.frame.append_bytes_inp(
                    delta_bytes,
                )
        self._last_update_time = current_time

        for incoming_frame in self._incoming_buffers.values():
            current_frame_length = incoming_frame.frame.length_frames
            if current_frame_length > stream_start_frames:
                incoming_frame.streaming = True
            elif current_frame_length < stream_end_frames:
                incoming_frame.streaming = False

        selected_frame_containers: list[FrameContainer] = [
            incoming_frame.frame
            for incoming_frame in self._incoming_buffers.values()
            if incoming_frame.streaming
        ]

        if len(selected_frame_containers) == 0:
            return b""

        audio_matrix = np.zeros(
            (
                len(selected_frame_containers),
                batch_length_frames,
            ),
            dtype=self._output_buffer.audio_format.numpy_format,
        )
        for i, selected_frame in enumerate(selected_frame_containers):
            audio_matrix[i] = np.frombuffer(
                selected_frame.get_begin_frames(batch_length_frames).frame_data,
                dtype=self._output_buffer.audio_format.numpy_format,
            )

        for ibuffer in self._incoming_buffers.values():
            if ibuffer.streaming:
                ibuffer.frame = ibuffer.frame.get_end_frames(
                    ibuffer.frame.length_frames - batch_length_frames,
                )

        audio_matrix = np.divide(audio_matrix, self._inputs_count)
        audio_matrix = np.sum(audio_matrix, axis=0)

        return cast(
            bytes,
            audio_matrix.astype(
                self._output_buffer.audio_format.numpy_format,
            ).tobytes(),
        )
