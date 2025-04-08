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

        self.preprocess_neuro_config()

    def preprocess_neuro_config(self) -> None:
        # Preprocess neuro config
        def load_from_file(file_path: str) -> str:
            with open(file_path) as fp:
                return fp.read()

        translate_map = self._neuro_config["translate"]
        swappable_keys = [
            "text_template",
            "correction_template",
            "gate_template",
            "gate_partial",
            "unified_template",
        ]
        for key in swappable_keys:
            if key in translate_map and translate_map[key].startswith("file://"):
                translate_map[key] = load_from_file(translate_map[key][7:])

    def run(self) -> None:
        logger.info("Starting Synchro instance")

        nodes, edges = GraphInitializer(
            self._settings,
            self._pipeline_config,
            self._neuro_config,
            self._events_cb,
        ).build()
        full_graph = GraphManager(nodes, edges, self._settings)
        full_graph.execute()

        logger.info("Stopping Synchro instance")
