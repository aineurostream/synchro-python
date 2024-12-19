import logging
from typing import Any

from synchro.config.schemas import ProcessingGraphConfig
from synchro.graph.graph_initializer import GraphInitializer
from synchro.graph.graph_manager import GraphManager

logger = logging.getLogger(__name__)


class CoreManager:
    def __init__(
        self,
        pipeline_config: ProcessingGraphConfig,
        neuro_config: dict[str, Any],
    ) -> None:
        self._pipeline_config = pipeline_config
        self._neuro_config = neuro_config

    def run(self) -> None:
        logger.info("Starting Synchro instance")

        nodes, edges = GraphInitializer(
            self._pipeline_config,
            self._neuro_config,
        ).build()
        full_graph = GraphManager(nodes, edges)
        full_graph.execute()

        logger.info("Stopping Synchro instance")
