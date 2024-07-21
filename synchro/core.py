import logging
import time
from contextlib import suppress
from queue import Empty
from threading import Thread

import pyaudio

from synchro.commons.types import ChannelLocale
from synchro.input_output.audio_device_manager import AudioDeviceManager
from synchro.input_output.audio_dispatcher import AudioDispatcher
from synchro.input_output.audio_stream_capture import AudioStreamInput
from synchro.input_output.audio_stream_output import AudioStreamOutput
from synchro.input_output.schemas import (
    InputAudioStreamConfig,
    InputStreamEntity,
    OutputAudioStreamConfig,
    OutputStreamEntity,
)

logger = logging.getLogger(__name__)


class CoreManager:
    def __init__(self, audio_format: str, rate: int, chunk_size: int) -> None:
        self._audio_format = audio_format
        self._rate = rate
        self._chunk_size = chunk_size
        self._inputs: list[InputStreamEntity] = []
        self._outputs: list[OutputStreamEntity] = []
        self._audio_dispatcher = AudioDispatcher(self._inputs, self._outputs)

        self._is_running = False

    def create_input_stream(self, conf_base: ChannelLocale) -> None:
        if self._is_running:
            raise RuntimeError("Cannot create input stream while running")

        config = InputAudioStreamConfig(
            device=conf_base.device,
            language=conf_base.language,
            audio_format=getattr(pyaudio, f"pa{self._audio_format}"),
            channels=1,
            rate=self._rate,
            chunk_size=self._chunk_size,
        )
        self._inputs.append(
            InputStreamEntity(
                id=len(self._inputs),
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
            rate=self._rate,
        )

        self._outputs.append(
            OutputStreamEntity(
                id=len(self._outputs),
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
                frames = stream.get_speech_frames()
                entity.queue.put(frames)
        logger.info(f"Finished input stream for {entity.id}/{entity.config.language}")

    def _thread_output_stream(
        self,
        manager: AudioDeviceManager,
        entity: OutputStreamEntity,
    ) -> None:
        logger.info(f"Starting output stream for {entity.id}/{entity.config.language}")
        with AudioStreamOutput(manager, entity.config) as stream:
            while self._is_running:
                logger.debug(f"Writing audio frames for {entity.config.language}")
                with suppress(Empty):
                    frames = entity.queue.get(timeout=0.1)
                    stream.write_audio_frames(frames)
        logger.info(f"Finished output stream for {entity.id}/{entity.config.language}")

    def _thread_dispatcher(self) -> None:
        logger.info("Starting audio dispatcher")
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
