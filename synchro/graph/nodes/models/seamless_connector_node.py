import json
import uuid
from types import TracebackType
from typing import TYPE_CHECKING, Any, Literal, Self

from socketio import SimpleClient
from socketio.exceptions import TimeoutError as SioTimeoutError

from synchro.config.audio_format import AudioFormat, AudioFormatType
from synchro.config.commons import StreamConfig
from synchro.config.schemas import SeamlessConnectorNodeSchema
from synchro.graph.graph_frame_container import GraphFrameContainer
from synchro.graph.graph_node import (
    EmittingNodeMixin,
    GraphNode,
    ReceivingNodeMixin,
)

if TYPE_CHECKING:
    from io import TextIOWrapper

INT16_MAX = 32767
DEFAULT_INPUT_RATE = 16000
DEFAULT_OUTPUT_RATE = 22050


class SeamlessConnectorNode(GraphNode, ReceivingNodeMixin, EmittingNodeMixin):
    def __init__(
        self,
        config: SeamlessConnectorNodeSchema,
        neuro_config: dict[str, Any],
    ) -> None:
        super().__init__(config.name)
        self._config = config
        self._neuro_config = neuro_config
        self._client = SimpleClient()
        self._buffer = b""
        self._user_id = str(uuid.uuid4())
        self._room_id = str(uuid.uuid4())[:4]
        self._connected = False
        self._log_file_path = config.log_file
        self._log_file: TextIOWrapper | None = None

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

        if self._log_file_path is not None:
            self._log_file = open(self._log_file_path, "w")  # noqa: SIM115

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> Literal[False]:
        self._client.disconnect()
        self._connected = False
        if self._log_file is not None:
            self._log_file.close()
            self._log_file = None

        return False

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

    def get_data(self) -> GraphFrameContainer | None:
        has_incoming_messages = True
        audio_result = b""
        while has_incoming_messages:
            try:
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
                    self._logger.info(log_message)
                    if self._log_file is not None:
                        self._log_file.write(
                            f"{json.dumps(log_body, separators=(',', ':'))}\n",
                        )
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
                language=self._config.lang_to,
                audio_format=AudioFormat(format_type=AudioFormatType.INT_16),
                rate=DEFAULT_OUTPUT_RATE,
            ),
            audio_result,
        )

    def is_active(self) -> bool:
        raise self._client.connected
