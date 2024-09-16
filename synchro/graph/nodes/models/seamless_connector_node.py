import uuid
from types import TracebackType
from typing import ClassVar, Literal, Self

import numpy as np
from socketio import SimpleClient
from socketio.exceptions import TimeoutError as SioTimeoutError

from synchro.config.audio_format import AudioFormat, AudioFormatType
from synchro.config.commons import StreamConfig
from synchro.config.schemas import SeamlessConnectorNodeSchema
from synchro.graph.graph_frame_container import GraphFrameContainer
from synchro.graph.graph_node import (
    ContextualGraphNode,
    EmittingNodeMixin,
    ReceivingNodeMixin,
)

INT16_MAX = 32767
DEFAULT_OUTPUT_RATE = 16000


class SeamlessConnectorNode(ContextualGraphNode, ReceivingNodeMixin, EmittingNodeMixin):
    LANGUAGES_MAP: ClassVar[dict[str, str]] = {
        "en": "eng",
        "ru": "rus",
        "fr": "fra",
        "ch": "cmn",
        "de": "deu",
    }

    def __init__(
        self,
        config: SeamlessConnectorNodeSchema,
    ) -> None:
        super().__init__(config.name)
        self._config = config
        self._client = SimpleClient()
        self._buffer = b""
        self._user_id = str(uuid.uuid4())
        self._room_id = str(uuid.uuid4())[:4]
        self._connected = False

    def __enter__(self) -> Self:
        if self._client.connected:
            raise RuntimeError("Client already connected")

        url = self._config.server_url
        from_language = self._config.from_language
        to_language = self._config.to_language

        self._logger.debug("Connecting to %s", url)
        self._client.connect(
            f"{url}/?clientID={self._user_id}",
            transports=["websocket"],
            socketio_path="/ws/socket.io",
        )
        self._logger.debug("Connected to %s with SID: %s", url, self._client.sid)
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

        if to_language not in self.LANGUAGES_MAP:
            raise ValueError(
                f"Unsupported language {to_language}"
                f" - add to language map if needed",
            )

        if from_language not in self.LANGUAGES_MAP:
            raise ValueError(
                f"Unsupported language {from_language}"
                f" - add to language map if needed",
            )

        language_to_sc = self.LANGUAGES_MAP[to_language]
        language_from_sc = self.LANGUAGES_MAP[from_language]

        self._logger.debug("Joined room %s in %s", self._room_id, self._client.sid)
        self._client.emit(
            "set_dynamic_config",
            {
                "source_language": language_from_sc,
                "target_language": language_to_sc,
                "expressive": None,
            },
        )
        self._logger.debug(
            "Set dynamic config for %s to %s",
            self._client.sid,
            language_to_sc,
        )

        self._client.emit(
            "configure_stream",
            {
                "event": "config",
                "rate": DEFAULT_OUTPUT_RATE,
                "model_name": "SeamlessStreaming",
                "model_type": "s2s&t",
                "debug": False,
                "async_processing": True,
                "buffer_limit": 1,
            },
        )
        self._logger.debug("Configured stream for %s", self._client.sid)
        self._connected = True

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> Literal[False]:
        self._client.disconnect()
        self._connected = False

        return False

    def initialize_edges(
        self,
        inputs: list[StreamConfig],
        outputs: list[StreamConfig],
    ) -> None:
        self.check_inputs_count(inputs, 1)
        self.check_has_outputs(outputs)

    def predict_config(
        self,
        _inputs: list[StreamConfig],
    ) -> StreamConfig:
        return StreamConfig(
            language=self._config.to_language,
            audio_format=AudioFormat(format_type=AudioFormatType.INT_16),
            rate=DEFAULT_OUTPUT_RATE,
        )

    def put_data(self, data: list[GraphFrameContainer]) -> None:
        if len(data) != 1:
            raise ValueError("Expected one frame container")

        samples = data[0].frame_data
        if len(samples) > 0:
            self._buffer += samples

        if len(self._buffer) > 0 and self._connected:
            self._client.emit(
                "incoming_audio",
                self._buffer,
            )
            self._logger.debug("Sent %d bytes to %s", len(samples), self._client.sid)
            self._buffer = b""

    def get_data(self) -> GraphFrameContainer:
        has_incoming_messages = True
        audio_result = b""
        raw_rate = DEFAULT_OUTPUT_RATE
        while has_incoming_messages:
            try:
                received_message = self._client.receive(timeout=0.01)
                if received_message[0] == "translation_speech":
                    self._logger.info(
                        "ATG: Received audio message: %s",
                        received_message[0],
                    )
                    data = received_message[1]
                    raw_rate = data["sample_rate"]
                    raw_payload: list[float] = data["payload"]
                    raw_float_payload = np.asarray(raw_payload)
                    int16_payload = (raw_float_payload * INT16_MAX).astype(np.int16)
                    converted_payload = int16_payload.tobytes()
                    audio_result += converted_payload
                else:
                    self._logger.debug(
                        "ATG: Received non-audio message: %s",
                        received_message,
                    )
            except SioTimeoutError:
                has_incoming_messages = False

        if len(audio_result) > 0:
            self._logger.debug(
                "Received %d bytes from %s",
                len(audio_result),
                self._client.sid,
            )

        return GraphFrameContainer.from_config(
            self.name,
            StreamConfig(
                language=self._config.to_language,
                audio_format=AudioFormat(format_type=AudioFormatType.INT_16),
                rate=raw_rate,
            ),
            audio_result,
        )

    def is_active(self) -> bool:
        raise self._client.connected
