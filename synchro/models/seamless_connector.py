import logging
import uuid
from types import TracebackType
from typing import ClassVar, Literal, Self

import librosa
import numpy as np
from socketio import SimpleClient
from socketio.exceptions import TimeoutError as SioTimeoutError

from synchro.input_output.schemas import InputAudioStreamConfig, OutputAudioStreamConfig
from synchro.models.base_model_connector import BaseModelConnector

INT16_MAX = 32767

logger = logging.getLogger(__name__)


class SeamlessMetaModelConnector(BaseModelConnector):
    LANGUAGES_MAP: ClassVar[dict[str, str]] = {
        "en": "eng",
        "ru": "rus",
    }

    def __init__(
        self,
        server_url: str,
        source_id: str,
        input_config: InputAudioStreamConfig,
        output_config: OutputAudioStreamConfig,
    ) -> None:
        super().__init__(source_id, input_config, output_config)
        self._server_url = server_url
        self._client = SimpleClient()
        self._user_id = str(uuid.uuid4())
        self._room_id = str(uuid.uuid4())[:4]

    def __enter__(self) -> Self:
        if self._client.connected:
            raise RuntimeError("Client already connected")

        logger.debug("Connecting to %s", self._server_url)
        self._client.connect(
            f"{self._server_url}/?clientID={self._user_id}",
            transports=["websocket"],
            socketio_path="/ws/socket.io",
        )
        logger.debug("Connected to %s with SID: %s", self._server_url, self._client.sid)
        self._client.emit(
            "join_room",
            (
                self._user_id,
                self._room_id,
                {
                    "roles": ["speaker", "listener"],
                    "lockServerName": None,
                },
            ),
        )

        if self.to_language not in self.LANGUAGES_MAP:
            raise ValueError(
                f"Unsupported language {self.to_language}"
                f" - add to language map if needed",
            )

        language_to_sc = self.LANGUAGES_MAP[self.to_language]

        logger.debug("Joined room %s in %s", self._room_id, self._client.sid)
        self._client.emit(
            "set_dynamic_config",
            {"target_language": language_to_sc, "expressive": None},
        )
        logger.debug(
            "Set dynamic config for %s to %s",
            self._client.sid,
            language_to_sc,
        )

        self._client.emit(
            "configure_stream",
            {
                "event": "config",
                "rate": self.input_rate,
                "model_name": "SeamlessStreaming",
                "model_type": "s2s&t",
                "debug": False,
                "async_processing": True,
                "buffer_limit": 1,
            },
        )
        logger.debug("Configured stream for %s", self._client.sid)

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> Literal[False]:
        self._client.disconnect()

        return False

    def send(self, samples: bytes) -> None:
        if len(samples) > 0:
            self._client.emit(
                "incoming_audio",
                samples,
            )
            logger.debug("Sent %d bytes to %s", len(samples), self._client.sid)

    def receive(self) -> bytes:
        has_incoming_messages = True
        audio_result = b""
        while has_incoming_messages:
            try:
                received_message = self._client.receive(timeout=0.01)
                if received_message[0] == "translation_speech":
                    logger.debug("ATG: Received audio message: %s", received_message[0])
                    data = received_message[1]
                    raw_rate = data["sample_rate"]
                    raw_payload: list[float] = data["payload"]
                    raw_float_payload = np.asarray(raw_payload)

                    if raw_rate != self._output_config.rate:
                        logger.debug(
                            "Resampling from %d to %d",
                            raw_rate,
                            self._output_config.rate,
                        )
                        raw_float_payload = librosa.resample(
                            raw_float_payload,
                            orig_sr=raw_rate,
                            target_sr=self._output_config.rate,
                        )

                    int16_payload = (raw_float_payload * INT16_MAX).astype(np.int16)

                    converted_payload = int16_payload.tobytes()
                    audio_result += converted_payload
                else:
                    logger.debug(
                        "ATG: Received non-audio message: %s",
                        received_message,
                    )
            except SioTimeoutError:
                has_incoming_messages = False
        logger.debug("Received %d bytes from %s", len(audio_result), self._client.sid)

        return audio_result

    def is_active(self) -> bool:
        raise self._client.connected

    def __str__(self) -> str:
        return f"SeamlessMetaModelConnector({self.from_language}->{self.to_language})"
