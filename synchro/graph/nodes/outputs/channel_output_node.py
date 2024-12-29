import logging
import time
from types import TracebackType
from typing import Literal, Self

import numpy as np
import sounddevice as sd

from synchro.config.commons import (
    MIN_STEP_LENGTH_SECS,
)
from synchro.config.schemas import OutputChannelStreamerNodeSchema
from synchro.graph.graph_frame_container import GraphFrameContainer
from synchro.graph.nodes.outputs.abstract_output_node import AbstractOutputNode

logger = logging.getLogger(__name__)


PREFILL_SECONDS = 2


class ChannelOutputNode(AbstractOutputNode):
    def __init__(
        self,
        config: OutputChannelStreamerNodeSchema,
    ) -> None:
        super().__init__(config.name)
        self._config = config
        self._stream: sd.OutputStream | None = None
        self._last_time_emit = 0.0
        self._out_buffer = b""

    def __enter__(self) -> Self:
        def callback(
            outdata: np.ndarray,
            frames: int,
            _time: int,
            status: str | None,
        ) -> None:
            if status:
                logger.error("Error in audio stream: %s", status)

            outgoing_buffer = np.frombuffer(self._out_buffer, dtype=np.int16)
            available_size = min(frames, outgoing_buffer.size)
            outdata[:available_size, 0] = outgoing_buffer[:available_size]
            self._out_buffer = outgoing_buffer[available_size:].tobytes()

        device_info = sd.query_devices(self._config.device, "output")
        self._stream = sd.OutputStream(
            device=self._config.device,
            channels=self._config.channel,
            samplerate=device_info["default_samplerate"],
            dtype=self._config.stream.audio_format.numpy_format,
            callback=callback,
        )
        self._stream.start()

        prefill_frames = int(self._config.stream.rate * PREFILL_SECONDS)
        self._out_buffer += np.zeros((prefill_frames,), dtype=np.int16).tobytes()

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> Literal[False]:
        if self._stream:
            self._stream.stop()
            self._stream.close()

        return False

    def put_data(self, frames: list[GraphFrameContainer]) -> None:
        active_frame = frames[0]
        logger.info(
            f"Writing {active_frame.length_frames()} frames to stream",
            extra={
                "frames": active_frame.length_frames(),
                "rate": active_frame.rate,
                "length": active_frame.length_secs(),
                "event": "audio_write",
                "node": self.name,
                "node_type": "channel_output",
            }
        )

        if len(frames) != 1:
            raise ValueError("Expected one frame container")

        if self._stream is None:
            raise RuntimeError("Audio stream is not open")

        frames_per_buffer = int(
            self._config.stream.rate * MIN_STEP_LENGTH_SECS,
        )

        if frames_per_buffer > active_frame.length_frames():
            raise ValueError(
                f"Expected {frames_per_buffer} frames, "
                f"got {active_frame.length_frames()}",
            )

        current_emit_time = time.time()
        if self._last_time_emit > 0:
            time_diff = current_emit_time - self._last_time_emit
            if time_diff > active_frame.length_secs():
                logger.warning(
                    "Time diff is %.3f while expected %.3f",
                    time_diff,
                    active_frame.length_secs(),
                )

        self._out_buffer += active_frame.frame_data
        self._last_time_emit = current_emit_time
