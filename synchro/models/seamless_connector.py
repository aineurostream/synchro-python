import logging
from types import TracebackType
from typing import Literal, Self

from socketio import Client

from synchro.input_output.schemas import InputAudioStreamConfig, OutputAudioStreamConfig
from synchro.models.base_model_connector import BaseModelConnector

logger = logging.getLogger(__name__)


class SeamlessMetaModelConnector(BaseModelConnector):
    def __init__(
        self,
        server_url: str,
        input_config: InputAudioStreamConfig,
        output_config: OutputAudioStreamConfig,
    ) -> None:
        super().__init__(input_config, output_config)
        self._server_url = server_url
        self._client = Client()

        self.register_callbacks()

    def register_callbacks(self) -> None:
        @self._client.event
        def connect() -> None:
            logger.info(
                "Connection established to %s (%s->%s)",
                self._server_url,
                self.from_language,
                self.to_language,
            )

        @self._client.event
        def disconnect() -> None:
            logger.info(
                "Disconnected from %s (%s->%s)",
                self._server_url,
                self.from_language,
                self.to_language,
            )

    def __enter__(self) -> Self:
        if self._client.connected:
            raise RuntimeError("Client already connected")

        self._client.connect(self._server_url)

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
        raise NotImplementedError

    def receive(self) -> bytes:
        raise NotImplementedError
