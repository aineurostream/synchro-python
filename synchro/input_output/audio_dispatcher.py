import logging
from contextlib import suppress
from queue import Empty
from types import TracebackType
from typing import Literal, Self

from synchro.input_output.audio_mixer import AudioMixer
from synchro.input_output.audio_stream_capture import SAMPLE_SIZE_BYTES_INT_16
from synchro.input_output.frame_container import FrameContainer, InputFrameContainer
from synchro.input_output.schemas import InputStreamEntity, OutputStreamEntity
from synchro.models.connector_manager import ConnectorManager

logger = logging.getLogger(__name__)


class AudioDispatcher:
    def __init__(
        self,
        server_url: str,
    ) -> None:
        self._server_url = server_url
        self._source_merged_inputs: dict[str, FrameContainer] = {}
        self._lang_containers_output: dict[str, FrameContainer] = {}
        self._audio_mixer = AudioMixer()
        self._connector_manager = ConnectorManager(self._server_url)
        self._inputs: list[InputStreamEntity] = []
        self._outputs: list[OutputStreamEntity] = []

    def __enter__(self) -> Self:
        self._connector_manager.activate()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> Literal[False]:
        self._connector_manager.deactivate()
        return False

    def initialize(
        self,
        inputs: list[InputStreamEntity],
        outputs: list[OutputStreamEntity],
    ) -> None:
        self._inputs = inputs
        self._outputs = outputs
        self._connector_manager.initialize(inputs, outputs)

    def process_batch(self) -> None:
        self._process_inputs()
        self._process_connectors()
        self._process_outputs()

    def _process_inputs(self) -> None:
        for process in self._inputs:
            if process.id not in self._source_merged_inputs:
                self._source_merged_inputs[process.id] = (
                    InputFrameContainer.create_empty(
                        process,
                    )
                )

            frame_container = self._source_merged_inputs[process.id]
            with suppress(Empty):
                while not process.queue.empty():
                    received_container: FrameContainer = process.queue.get(block=False)
                    logger.debug(
                        "Appending %d bytes from %s/%s",
                        len(received_container.frame_data),
                        process.id,
                        process.config.language,
                    )
                    frame_container.append(received_container)

    def _process_connectors(self) -> None:
        for process in self._inputs:
            if process.id in self._source_merged_inputs:
                merged_input = self._source_merged_inputs[process.id]
                if len(merged_input) > 0:
                    self._connector_manager.send(
                        process.id,
                        FrameContainer(
                            sample_size=merged_input.sample_size,
                            rate=merged_input.rate,
                            frame_data=merged_input.frame_data,
                        ),
                    )
                    logger.debug(
                        "Sent %d bytes to %s connector",
                        len(merged_input.frame_data),
                        process.id,
                    )
                    merged_input.clear()

        for output in self._outputs:
            received_data = self._connector_manager.receive(output.config.language)
            if len(received_data) == 0:
                continue

            mixed_frames = self._audio_mixer.mix_frames(received_data)
            if output.config.language not in self._lang_containers_output:
                self._lang_containers_output[output.config.language] = FrameContainer(
                    sample_size=SAMPLE_SIZE_BYTES_INT_16,
                    rate=output.config.rate,
                    frame_data=b"",
                )

            logger.debug(
                "Merging %d bytes for %s connector",
                len(mixed_frames),
                output.id,
            )
            self._lang_containers_output[output.config.language].append_bytes(
                mixed_frames,
            )

    def _process_outputs(self) -> None:
        for process in self._outputs:
            with suppress(Empty):
                if process.config.language not in self._lang_containers_output:
                    continue

                output_frame_data: FrameContainer = self._lang_containers_output[
                    process.config.language
                ]
                if len(output_frame_data) > 0:
                    logger.debug(
                        "Outputting %d bytes to %s/%s",
                        len(output_frame_data),
                        process.id,
                        process.config.language,
                    )
                    process.queue.put(output_frame_data.frame_data)

        for output_frame_data in self._lang_containers_output.values():
            output_frame_data.clear()
