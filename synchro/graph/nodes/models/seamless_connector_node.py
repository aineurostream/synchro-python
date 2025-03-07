import contextlib
import uuid
from types import TracebackType
from typing import Any, Literal, Self, cast

from socketio import SimpleClient
from socketio.exceptions import TimeoutError as SioTimeoutError

from synchro.audio.frame_container import FrameContainer
from synchro.config.audio_format import DEFAULT_AUDIO_FORMAT
from synchro.config.commons import NodeEventsCallback, StreamConfig
from synchro.config.schemas import SeamlessConnectorNodeSchema
from synchro.graph.graph_node import (
    EmittingNodeMixin,
    GraphNode,
    ReceivingNodeMixin,
)

INT16_MAX = 32767
DEFAULT_INPUT_RATE = 16000
DEFAULT_OUTPUT_RATE = 22050


class SeamlessConnectorNode(GraphNode, ReceivingNodeMixin, EmittingNodeMixin):
    def __init__(
        self,
        config: SeamlessConnectorNodeSchema,
        neuro_config: dict[str, Any],
        events_cb: NodeEventsCallback | None = None,
    ) -> None:
        super().__init__(config.name)
        self._config = config
        self._neuro_config = neuro_config
        self._client = SimpleClient()
        self._buffer_bytes = b""
        self._user_id = str(uuid.uuid4())
        self._room_id = str(uuid.uuid4())[:4]
        self._connected = False
        self._events_cb = events_cb
        self._stream_config = StreamConfig(
            audio_format=DEFAULT_AUDIO_FORMAT,
            rate=DEFAULT_OUTPUT_RATE,
        )

    def __enter__(self) -> Self:
        if self._client.connected:
            raise RuntimeError("Client already connected")

        url = self._config.server_url

        self._logger.debug("Connecting to %s", url)
        self._client.connect(
            str(url),
            transports=["websocket"],
            socketio_path="/ws/socket.io",
        )
        self._logger.debug("Connected to %s with SID: %s", url, self._client.sid)

        self._client.emit(
            "configure_stream",
            {
                "lang": {
                    "source": self._config.lang_from,
                    "target": self._config.lang_to,
                },
                **self._neuro_config,
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

    def put_data(self, _source: str, data: FrameContainer) -> None:
        samples = data.frame_data
        if len(samples) > 0:
            self._buffer_bytes += samples

        if len(self._buffer_bytes) > 0 and self._connected:
            self._client.emit(
                "incoming_audio",
                self._buffer_bytes,
            )
            self._logger.debug("Sent %d bytes to %s", len(samples), self._client.sid)
            self._buffer_bytes = b""

    def get_data(self) -> FrameContainer | None:
        audio_result = b""
        with contextlib.suppress(SioTimeoutError):
            while True:
                received_message = self._client.receive(timeout=0.01)
                if received_message[0] == "translation_speech":
                    self._logger.info(
                        "ATG: Received audio message: %s",
                        received_message[0],
                    )
                    audio_result += received_message[1]
                elif received_message[0] == "log":
                    log_body = received_message[1]
                    context = log_body["context"]
                    log_message = (
                        f"{context['time']} - {log_body['id']} "
                        f"{log_body['part']}: {context['message']}"
                    )
                    self._logger.info(log_message, extra=log_body)
                    if self._events_cb:
                        self._events_cb(
                            self.name,
                            log_body,
                        )
                else:
                    self._logger.warning(
                        "ATG: Received unsupported non-audio message: %s",
                        received_message,
                    )
        if len(audio_result) > 0:
            self._logger.debug(
                "Received %d bytes from %s",
                len(audio_result),
                self._client.sid,
            )
        return FrameContainer.from_config(
            self._stream_config,
            audio_result,
        )

    def is_active(self) -> bool:
        return cast(bool, self._client.connected)
