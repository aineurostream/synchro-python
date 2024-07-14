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
            channels=conf_base.channel,
            rate=self._rate,
            chunk_size=self._chunk_size,
        )
        self._inputs.append(
            InputStreamEntity(
                id=len(self._inputs),
                config=config,
            ),
        )

    def create_output_stream(self, conf_base: ChannelLocale) -> None:
        if self._is_running:
            raise RuntimeError("Cannot create output stream while running")

        config = OutputAudioStreamConfig(
            device=conf_base.device,
            language=conf_base.language,
            audio_format=getattr(pyaudio, f"pa{self._audio_format}"),
            channels=conf_base.channel,
            rate=self._rate,
        )

        self._outputs.append(
            OutputStreamEntity(
                id=len(self._outputs),
                config=config,
            ),
        )

    def _thread_input_stream(
        self,
        manager: AudioDeviceManager,
        entity: InputStreamEntity,
    ) -> None:
        with AudioStreamInput(manager, entity.config) as stream:
            while self._is_running:
                frames = stream.get_audio_frames()
                entity.queue.put(frames)

    def _thread_output_stream(
        self,
        manager: AudioDeviceManager,
        entity: OutputStreamEntity,
    ) -> None:
        with AudioStreamOutput(manager, entity.config) as stream:
            while self._is_running:
                frames = entity.queue.get()
                stream.write_audio_frames(frames)

    def _thread_dispatcher(self) -> None:
        while self._is_running:
            self._audio_dispatcher.process_batch()

    def run(self) -> None:
        self._is_running = True
        active_threads: list[Thread] = []

        def activate_thread(created_thread: Thread) -> None:
            created_thread.start()
            active_threads.append(created_thread)

        try:
            with AudioDeviceManager() as manager:
                for in_channel in self._inputs:
                    activate_thread(
                        Thread(
                            target=self._thread_input_stream,
                            args=(manager, in_channel),
                        ),
                    )

                for out_channel in self._outputs:
                    activate_thread(
                        Thread(
                            target=self._thread_output_stream,
                            args=(manager, out_channel),
                        ),
                    )

                activate_thread(
                    Thread(
                        target=self._thread_dispatcher,
                    ),
                )

        finally:
            self._is_running = False
            for thread in active_threads:
                thread.join()
