import logging
import time
from contextlib import suppress
from queue import Empty
from threading import Thread

import pyaudio

from synchro.commons.types import ChannelLocale
from synchro.input_output.audio_device_manager import AudioDeviceManager
from synchro.input_output.audio_dispatcher import AudioDispatcher
from synchro.input_output.audio_stream_capture import (
    SAMPLE_SIZE_BYTES_INT_16,
    AudioStreamInput,
)
from synchro.input_output.audio_stream_output import AudioStreamOutput
from synchro.input_output.frame_container import FrameContainer
from synchro.input_output.schemas import (
    InputAudioStreamConfig,
    InputStreamEntity,
    OutputAudioStreamConfig,
    OutputStreamEntity,
)

logger = logging.getLogger(__name__)


class CoreManager:
    def __init__(
        self,
        server_url: str,
        audio_format: str,
        rate: int | None,
        chunk_size: int,
    ) -> None:
        self._audio_format = audio_format
        self._rate = rate
        self._chunk_size = chunk_size
        self._inputs: list[InputStreamEntity] = []
        self._outputs: list[OutputStreamEntity] = []
        self._audio_dispatcher = AudioDispatcher(server_url)
        self._devices = {
            device.index: device for device in AudioDeviceManager.list_audio_devices()
        }
        self._is_running = False

    def create_input_stream(self, conf_base: ChannelLocale) -> None:
        if self._is_running:
            raise RuntimeError("Cannot create input stream while running")

        if conf_base.device not in self._devices:
            raise RuntimeError(f"Device with ID {conf_base.device} not found")

        config = InputAudioStreamConfig(
            device=conf_base.device,
            language=conf_base.language,
            audio_format=getattr(pyaudio, f"pa{self._audio_format}"),
            channels=1,
            rate=self._rate
            if self._rate
            else self._devices[conf_base.device].default_sample_rate,
            chunk_size=self._chunk_size,
        )
        self._inputs.append(
            InputStreamEntity(
                id=f"INPUT_{len(self._inputs)}",
                config=config,
            ),
        )
        logger.info(f"Created input stream conf for {conf_base}")

    def create_output_stream(self, conf_base: ChannelLocale) -> None:
        if self._is_running:
            raise RuntimeError("Cannot create output stream while running")

        config = OutputAudioStreamConfig(
            device=conf_base.device,
            language=conf_base.language,
            audio_format=getattr(pyaudio, f"pa{self._audio_format}"),
            channels=1,
            rate=self._rate
            if self._rate
            else self._devices[conf_base.device].default_sample_rate,
        )

        self._outputs.append(
            OutputStreamEntity(
                id=f"OUTPUT_{len(self._outputs)}",
                config=config,
            ),
        )
        logger.info(f"Created output stream conf for {conf_base}")

    def _thread_input_stream(
        self,
        manager: AudioDeviceManager,
        entity: InputStreamEntity,
    ) -> None:
        logger.info(f"Starting input stream for {entity.id}/{entity.config.language}")
        with AudioStreamInput(manager, entity.config) as stream:
            while self._is_running:
                logger.debug(f"Reading audio frames for {entity.config.language}")
                frame_bytes = stream.get_speech_frames()
                if len(frame_bytes) > 0:
                    frame_container = FrameContainer(
                        sample_size=SAMPLE_SIZE_BYTES_INT_16,
                        rate=entity.config.rate,
                        frame_data=frame_bytes,
                    )
                    logger.info(
                        f"Sending {len(frame_bytes)} bytes "
                        f"to {entity.id}/{entity.config.language}",
                    )
                    entity.queue.put(frame_container)
        logger.info(f"Finished input stream for {entity.id}/{entity.config.language}")

    def _thread_output_stream(
        self,
        manager: AudioDeviceManager,
        entity: OutputStreamEntity,
    ) -> None:
        logger.info(f"Starting output stream for {entity.id}/{entity.config.language}")
        with AudioStreamOutput(manager, entity.config) as stream:
            while self._is_running:
                logger.debug(
                    f"Writing audio frames for {entity.id}/{entity.config.language}",
                )
                with suppress(Empty):
                    frames = entity.queue.get(timeout=0.1)
                    if len(frames) > 0:
                        logger.debug(
                            f"Outputting {len(frames)} bytes "
                            f"to {entity.id}/{entity.config.language}",
                        )
                        stream.write_audio_frames(frames)
        logger.info(f"Finished output stream for {entity.id}/{entity.config.language}")

    def _thread_dispatcher(self) -> None:
        logger.info("Initializing audio dispatcher")
        self._audio_dispatcher.initialize(self._inputs, self._outputs)
        logger.info("Starting audio dispatcher")
        with self._audio_dispatcher:
            while self._is_running:
                self._audio_dispatcher.process_batch()
                time.sleep(0.01)
        logger.info("Finished audio dispatcher")

    def stop(self) -> None:
        logger.info("Stopping Synchro instance")
        self._is_running = False

    def run(self) -> None:
        logger.info("Starting Synchro instance")
        self._is_running = True
        active_threads: list[Thread] = []

        def activate_thread(created_thread: Thread) -> None:
            created_thread.start()
            active_threads.append(created_thread)

        with AudioDeviceManager() as manager:
            for index, in_channel in enumerate(self._inputs):
                activate_thread(
                    Thread(
                        name=f"input_stream_{index}",
                        target=self._thread_input_stream,
                        args=(manager, in_channel),
                    ),
                )

            for index, out_channel in enumerate(self._outputs):
                activate_thread(
                    Thread(
                        name=f"output_stream_{index}",
                        target=self._thread_output_stream,
                        args=(manager, out_channel),
                    ),
                )

            activate_thread(
                Thread(
                    target=self._thread_dispatcher,
                ),
            )

            # Wait for interruption
            with suppress(KeyboardInterrupt):
                while self._is_running:
                    time.sleep(0.1)

            self.stop()

            logger.info("Synchro instance stopped")

            logger.info("Waiting for threads to finish")
            for thread in active_threads:
                thread.join()
