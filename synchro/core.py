import logging

from synchro.audio.audio_device_manager import AudioDeviceManager
from synchro.config.schemas import ProcessingGraphConfig
from synchro.graph.graph_initializer import GraphInitializer
from synchro.graph.graph_manager import GraphManager

logger = logging.getLogger(__name__)


class CoreManager:
    def __init__(
        self,
        config: ProcessingGraphConfig,
    ) -> None:
        self._config = config

    def run(self) -> None:
        logger.info("Starting Synchro instance")

        with AudioDeviceManager() as manager:
            nodes, edges = GraphInitializer(self._config, manager).build()
            full_graph = GraphManager(nodes, edges)
            full_graph.execute()

        logger.info("Stopping Synchro instance")
