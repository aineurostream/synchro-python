from types import TracebackType
from typing import Literal, Self, cast

import sounddevice as sd
from pydub import AudioSegment, effects

from synchro.audio.voice_activity_detector import (
    VoiceActivityDetector,
    VoiceActivityDetectorResult,
)
from synchro.config.commons import (
    MIN_BUFFER_SIZE_SEC,
    PREFERRED_BUFFER_SIZE_SEC,
)
from synchro.config.schemas import InputChannelStreamerNodeSchema
from synchro.graph.graph_frame_container import GraphFrameContainer
from synchro.graph.nodes.inputs.abstract_input_node import AbstractInputNode


class ChannelInputNode(AbstractInputNode):
    def __init__(
        self,
        config: InputChannelStreamerNodeSchema,
    ) -> None:
        super().__init__(config.name)
        self._config = config
        self._vad = VoiceActivityDetector(
            sample_size_bytes=self._config.stream.audio_format.sample_size,
            sample_rate=config.stream.rate,
            min_buffer_size_sec=MIN_BUFFER_SIZE_SEC,
            shrink_buffer_size_sec=PREFERRED_BUFFER_SIZE_SEC,
        )
        self._stream: sd.InputStream | None = None
        self._incoming_buffer = b""

    def __enter__(self) -> Self:
        def callback(indata, frames, time, status):
            if status:
                self._logger.error("Error in audio stream: %s", status)
            self._incoming_buffer += cast(bytes, indata.tobytes())

        device_info = sd.query_devices(self._config.device, "input")
        self._stream = sd.InputStream(
            device=self._config.device,
            channels=self._config.channel,
            dtype=self._config.stream.audio_format.numpy_format,
            samplerate=device_info["default_samplerate"],
            callback=callback,
        )
        self._stream.start()

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

    def get_data(self) -> GraphFrameContainer:
        return GraphFrameContainer.from_config(
            self.name,
            self._config.stream,
            self._read_speech_frames(),
        )

    def _read_speech_frames(self) -> bytes:
        if not self._stream:
            raise RuntimeError("Audio stream is not open")

        read_bytes = self._incoming_buffer
        self._incoming_buffer = b""
        if len(read_bytes) > 0:
            read_bytes = self._normalize_audio(read_bytes)
            voice_result = self._vad.detect_voice(read_bytes)
            if voice_result == VoiceActivityDetectorResult.SPEECH:
                self._logger.debug("Detected speech: %d bytes", len(read_bytes))
                return read_bytes
        return b""

    def _normalize_audio(self, audio: bytes) -> bytes:
        audio_segment = AudioSegment(
            audio,
            frame_rate=self._config.stream.rate,
            sample_width=self._config.stream.audio_format.sample_size,
            channels=1,
        )
        audio_segment = effects.normalize(audio_segment, headroom=10.0)

        return cast(bytes, audio_segment.raw_data)
