import logging
from types import TracebackType
from typing import Literal, Self

import pyaudio

from synchro.audio.audio_device_manager import AudioDeviceManager
from synchro.config.commons import MIN_STEP_LENGTH_SECS, StreamConfig
from synchro.config.schemas import OutputChannelStreamerNodeSchema
from synchro.graph.graph_frame_container import GraphFrameContainer
from synchro.graph.nodes.outputs.abstract_output_node import AbstractOutputNode

logger = logging.getLogger(__name__)


class ChannelOutputNode(AbstractOutputNode):
    def __init__(
        self,
        config: OutputChannelStreamerNodeSchema,
        manager: AudioDeviceManager,
    ) -> None:
        super().__init__(config.name)
        self._config = config
        self._manager = manager
        self._stream: pyaudio.Stream | None = None
        self._prefilled = False

    def __enter__(self) -> Self:
        frames_per_buffer = int(
            self._config.stream.rate
            * MIN_STEP_LENGTH_SECS
        )

        self._stream = self._manager.context.open(
            format=self._config.stream.audio_format.pyaudio_format,
            channels=self._config.channel,
            rate=self._config.stream.rate,
            output=True,
            output_device_index=self._config.device,
            frames_per_buffer=frames_per_buffer,
        )

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> Literal[False]:
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()

        return False

    def initialize_edges(
        self,
        inputs: list[StreamConfig],
        outputs: list[StreamConfig],
    ) -> None:
        self.check_inputs_count(inputs, 1)
        self.check_outputs_count(outputs, 0)

        if inputs[0].audio_format != self._config.stream.audio_format:
            raise ValueError(
                f"Node {self} has AF {inputs[0].audio_format} "
                f"but expected {self._config.stream.audio_format}",
            )

        if inputs[0].rate != self._config.stream.rate:
            raise ValueError(
                f"Node {self} has rate {inputs[0].rate} "
                f"but expected {self._config.stream.rate}",
            )

    def predict_config(
        self,
        _inputs: list[StreamConfig],
    ) -> StreamConfig:
        return self._config.stream

    def put_data(self, frames: list[GraphFrameContainer]) -> None:
        logger.info(f"Writing {frames[0].length_frames()} frames to stream")

        if len(frames) != 1:
            raise ValueError("Expected one frame container")

        if self._stream is None:
            raise RuntimeError("Audio stream is not open")

        frames_per_buffer = int(
            self._config.stream.rate
            * MIN_STEP_LENGTH_SECS
        )

        if not self._prefilled:
            logger.info(f"Prefilling buffer for {frames_per_buffer} samples")
            prefill_bytes = frames_per_buffer * self._config.stream.rate
            self._stream.write(b"0" * prefill_bytes)
            self._prefilled = True

        if frames_per_buffer > frames[0].length_frames():
            raise ValueError(
                f"Expected {frames_per_buffer} frames, got {frames[0].length_frames()}",
            )

        self._stream.write(frames[0].frame_data)
