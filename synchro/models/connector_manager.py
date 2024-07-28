import logging
import time
from collections import defaultdict
from contextlib import suppress
from queue import Empty, Queue
from threading import Thread

from synchro.input_output.audio_stream_capture import SAMPLE_SIZE_BYTES_INT_16
from synchro.input_output.frame_container import FrameContainer
from synchro.input_output.schemas import InputStreamEntity, OutputStreamEntity
from synchro.models.base_model_connector import BaseModelConnector
from synchro.models.seamless_connector import SeamlessMetaModelConnector

SLEEPING_TIME_DEFAULT = 0.05

logger = logging.getLogger(__name__)


class ConnectorTask:
    def __init__(self, connector: BaseModelConnector) -> None:
        self.connector = connector
        self.incoming: Queue = Queue()
        self.outgoing: Queue = Queue()
        self.active = True

    def run(self) -> None:
        logger.info(
            "Starting connector task to %s",
            self.connector,
        )
        with self.connector as conn:
            while self.active:
                data = conn.receive()
                if len(data) > 0:
                    logger.debug(
                        "Received %d bytes from %s",
                        len(data),
                        self.connector,
                    )
                    self.outgoing.put(data)

                with suppress(Empty):
                    while not self.incoming.empty():
                        bytes_to_send: FrameContainer = self.incoming.get()
                        if len(bytes_to_send) > 0:
                            logger.debug(
                                "Sending %d bytes to %s",
                                len(bytes_to_send),
                                self.connector,
                            )
                            conn.send(bytes_to_send.frame_data)

                time.sleep(SLEEPING_TIME_DEFAULT)

            logger.info(
                """Closing connector task to %s""",
                self.connector,
            )


class ConnectorManager:
    def __init__(
        self,
        server_url: str,
    ) -> None:
        self._server_url = server_url
        self._inputs: dict[str, InputStreamEntity] = {}
        self._outputs: dict[str, OutputStreamEntity] = {}
        self._connectors: dict[str, BaseModelConnector] = {}
        self._sending_tasks: dict[str, ConnectorTask] = {}

    def initialize(
        self,
        inputs: list[InputStreamEntity],
        outputs: list[OutputStreamEntity],
    ) -> None:
        if len(self._inputs) > 0 or len(self._outputs) > 0:
            raise RuntimeError("Connector manager already initialized")

        self._inputs = {inp.id: inp for inp in inputs}
        self._outputs = {out.id: out for out in outputs}

        for input_entity in self._inputs.values():
            for output_entity in self._outputs.values():
                if output_entity.config.language != input_entity.config.language:
                    connector = SeamlessMetaModelConnector(
                        server_url=self._server_url,
                        source_id=input_entity.id,
                        input_config=input_entity.config,
                        output_config=output_entity.config,
                    )
                    self._connectors[connector.base_id] = connector
                    logger.debug("Created connector %s", connector)

    def activate(self) -> None:
        logger.info("Activating connectors")
        for connector in self._connectors.values():
            task = ConnectorTask(connector)
            self._sending_tasks[connector.base_id] = task
            thread = Thread(target=task.run)
            thread.start()
            logger.info(
                "Connector %s activated",
                connector,
            )

    def deactivate(self) -> None:
        logger.info("Deactivating connectors")
        for connector in self._connectors.values():
            task = self._sending_tasks.pop(connector.base_id)
            task.active = False
            logger.info(
                "Connector %s deactivated",
                connector,
            )

    def send(self, source_id: str, container: FrameContainer) -> None:
        for connector in self._connectors.values():
            if connector.source_id == source_id:
                task = self._sending_tasks[connector.base_id]
                task.incoming.put(container)
                logger.debug(
                    "Put %d bytes to %s",
                    len(container.frame_data),
                    connector,
                )

    def receive(self, to_language: str) -> list[FrameContainer]:
        full_data: dict[str, bytes] = defaultdict(lambda: b"")
        for connector in self._connectors.values():
            if connector.to_language == to_language:
                task = self._sending_tasks[connector.base_id]
                with suppress(Empty):
                    while not task.outgoing.empty():
                        data = task.outgoing.get(block=False)
                        full_data[connector.base_id] += data
                        logger.debug(
                            "Received %d bytes from %s",
                            len(data),
                            connector,
                        )

        returning_result: list[FrameContainer] = []
        for connector_id, frame_bytes in full_data.items():
            connector = self._connectors[connector_id]
            returning_result.append(
                FrameContainer(
                    sample_size=SAMPLE_SIZE_BYTES_INT_16,
                    rate=connector.input_rate,
                    frame_data=frame_bytes,
                ),
            )

        return returning_result
