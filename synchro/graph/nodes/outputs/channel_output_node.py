import logging
import time
from types import TracebackType
from typing import Literal, Self

import numpy as np
import sounddevice as sd

from synchro.audio.frame_container import FrameContainer
from synchro.config.audio_format import DEFAULT_AUDIO_FORMAT
from synchro.config.commons import (
    MIN_STEP_LENGTH_SECS,
)
from synchro.config.schemas import OutputChannelStreamerNodeSchema
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
        self._sample_rate = 0
        self._stream: sd.OutputStream | None = None
        self._last_time_emit = 0.0
        self._out_buffer = b""

    def __enter__(self) -> Self:
        def callback(
            out_data: np.ndarray,
            frames: int,
            _time: int,
            status: str | None,
        ) -> None:
            if status:
                self._logger.error("Error in audio stream: %s", status)

            outgoing_buffer = np.frombuffer(self._out_buffer, dtype=np.int16)
            available_size = min(frames, outgoing_buffer.size)
            if available_size > 0:
                out_data[:available_size, self._config.channel - 1] = outgoing_buffer[
                    :available_size
                ]
                if available_size < frames:
                    out_data[available_size:, self._config.channel - 1] = 0
            else:
                out_data[:, self._config.channel - 1] = 0
            self._out_buffer = outgoing_buffer[available_size:].tobytes()

        device_info = sd.query_devices(self._config.device, "output")
        self._sample_rate = device_info["default_samplerate"]
        self._stream = sd.OutputStream(
            device=self._config.device,
            channels=self._config.channel,
            samplerate=self._sample_rate,
            dtype=DEFAULT_AUDIO_FORMAT.numpy_format,
            callback=callback,
        )
        self._stream.start()
        prefill_frames = int(self._sample_rate * PREFILL_SECONDS)
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

    def put_data(self, _source: str, data: FrameContainer) -> None:
        if data.rate != self._sample_rate:
            self._logger.warning(
                "Data rate is %d, expected %d",
                data.rate,
                self._sample_rate,
            )

        self._logger.info(
            "Writing %d frames to stream",
            data.length_frames,
            extra={
                "frames": data.length_frames,
                "rate": data.rate,
                "length": data.length_secs,
                "event": "audio_write",
                "node": self.name,
                "node_type": "channel_output",
            },
        )
        if self._stream is None:
            raise RuntimeError("Audio stream is not open")
        frames_per_buffer = int(
            self._sample_rate * MIN_STEP_LENGTH_SECS,
        )
        if frames_per_buffer > data.length_frames:
            self._logger.warning(
                "Expected %d frames, got %d",
                frames_per_buffer,
                data.length_frames,
            )

        current_emit_time = time.time()
        if self._last_time_emit > 0:
            time_diff = current_emit_time - self._last_time_emit
            if time_diff > data.length_secs:
                self._logger.warning(
                    "Time diff is %.3f while expected %.3f",
                    time_diff,
                    data.length_secs,
                )
        self._out_buffer += data.frame_data
        self._last_time_emit = current_emit_time
