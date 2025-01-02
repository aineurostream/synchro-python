import logging
from typing import Any

from synchro.config.commons import NodeEventsCallback
from synchro.config.schemas import ProcessingGraphConfig
from synchro.config.settings import SettingsSchema
from synchro.graph.graph_initializer import GraphInitializer
from synchro.graph.graph_manager import GraphManager

logger = logging.getLogger(__name__)


class CoreManager:
    def __init__(
        self,
        pipeline_config: ProcessingGraphConfig,
        neuro_config: dict[str, Any],
        settings: SettingsSchema,
        events_cb: NodeEventsCallback | None = None,
    ) -> None:
        self._pipeline_config = pipeline_config
        self._neuro_config = neuro_config
        self._settings = settings
        self._events_cb = events_cb

    def run(self) -> None:
        logger.info("Starting Synchro instance")

        nodes, edges = GraphInitializer(
            self._pipeline_config,
            self._neuro_config,
            self._events_cb,
        ).build()
        full_graph = GraphManager(nodes, edges, self._settings)
        full_graph.execute()

        logger.info("Stopping Synchro instance")
