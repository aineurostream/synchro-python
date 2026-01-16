import logging
import typing
from collections.abc import Callable
from pathlib import Path
from typing import Any

from synchro.config.commons import NodeEventsCallback
from synchro.config.schemas import (
    AllNodeTypes,
    DenoiserNodeSchema,
    InputChannelStreamerNodeSchema,
    InputFileStreamerNodeSchema,
    MixerNodeSchema,
    NormalizerNodeSchema,
    OutputChannelStreamerNodeSchema,
    OutputFileNodeSchema,
    ProcessingGraphConfig,
    ResamplerNodeSchema,
    SeamlessConnectorNodeSchema,
    VadNodeSchema,
    FormatValidatorNodeSchema,
    WhisperPrepNodeSchema,
    TerminalMetricsDisplayNodeSchema,
)
from synchro.config.settings import SettingsSchema
from synchro.graph.graph_edge import GraphEdge
from synchro.graph.graph_node import GraphNode
from synchro.graph.nodes.inputs.channel_input_node import ChannelInputNode
from synchro.graph.nodes.inputs.file_input_node import FileInputNode
from synchro.graph.nodes.models.seamless_connector_node import SeamlessConnectorNode
from synchro.graph.nodes.outputs.channel_output_node import ChannelOutputNode
from synchro.graph.nodes.outputs.file_output_node import FileOutputNode
from synchro.graph.nodes.processors.denoiser_node import DenoiserNode
from synchro.graph.nodes.processors.mixer_node import MixerNode
from synchro.graph.nodes.processors.normalization_node import NormalizerNode
from synchro.graph.nodes.processors.resample_node import ResampleNode
from synchro.graph.nodes.processors.vad_node import VadNode
from synchro.graph.nodes.processors.preparation_node import WhisperPrepNode
from synchro.graph.nodes.processors.validation_node import FormatValidatorNode
from synchro.graph.nodes.outputs.metrics_node import TerminalMetricsDisplayNode

logger = logging.getLogger(__name__)

WORKING_DIR_KEY = "WORKING_DIR"


class GraphInitializer:
    def __init__(
        self,
        settings: SettingsSchema,
        config: ProcessingGraphConfig,
        neuro_config: dict[str, Any],
        events_cb: NodeEventsCallback | None = None,
        working_dir: str | None = None,
    ) -> None:
        self._settings = settings
        self._config = config
        self._neuro_config = neuro_config
        self._events_cb = events_cb
        self._working_dir = working_dir

    def _create_channel_input_node(
        self,
        config: InputChannelStreamerNodeSchema,
    ) -> ChannelInputNode:
        return ChannelInputNode(config)

    def _create_file_input_node(
        self,
        config: InputFileStreamerNodeSchema,
    ) -> FileInputNode:
        return FileInputNode(config)

    def _create_channel_output_node(
        self,
        config: OutputChannelStreamerNodeSchema,
    ) -> ChannelOutputNode:
        return ChannelOutputNode(config, self._settings.input_interval_secs)

    def _create_file_output_node(
        self,
        config: OutputFileNodeSchema,
    ) -> FileOutputNode:
        return FileOutputNode(config, Path(self._working_dir or ""))

    def _create_seamless_connector_node(
        self,
        config: SeamlessConnectorNodeSchema,
    ) -> SeamlessConnectorNode:
        return SeamlessConnectorNode(config, self._neuro_config, self._events_cb)

    def _create_mixer_node(self, config: MixerNodeSchema) -> MixerNode:
        return MixerNode(config)

    def _create_resample_node(self, config: ResamplerNodeSchema) -> ResampleNode:
        return ResampleNode(config)

    def _create_vad_node(self, config: VadNodeSchema) -> VadNode:
        return VadNode(config)

    def _create_normalizer_node(self, config: NormalizerNodeSchema) -> NormalizerNode:
        return NormalizerNode(config)

    def _create_denoiser_node(self, config: DenoiserNodeSchema) -> DenoiserNode:
        return DenoiserNode(config)

    def _create_validator_node(self, config: DenoiserNodeSchema) -> FormatValidatorNode:
        return FormatValidatorNode(config)

    def _create_preparer_node(self, config: DenoiserNodeSchema) -> WhisperPrepNode:
        return WhisperPrepNode(config)

    def _create_measurer_node(self, config: TerminalMetricsDisplayNodeSchema) -> TerminalMetricsDisplayNode:
        return TerminalMetricsDisplayNode(config)
    
    BUILD_METHODS: typing.ClassVar[
        dict[type, Callable[["GraphInitializer", Any], GraphNode]]
    ] = {
        InputChannelStreamerNodeSchema: _create_channel_input_node,
        InputFileStreamerNodeSchema: _create_file_input_node,
        OutputChannelStreamerNodeSchema: _create_channel_output_node,
        OutputFileNodeSchema: _create_file_output_node,
        SeamlessConnectorNodeSchema: _create_seamless_connector_node,
        MixerNodeSchema: _create_mixer_node,
        ResamplerNodeSchema: _create_resample_node,
        VadNodeSchema: _create_vad_node,
        NormalizerNodeSchema: _create_normalizer_node,
        DenoiserNodeSchema: _create_denoiser_node,
        FormatValidatorNodeSchema: _create_validator_node,
        WhisperPrepNodeSchema: _create_preparer_node,
        TerminalMetricsDisplayNodeSchema: _create_measurer_node,
    }

    def build(self) -> tuple[list[GraphNode], list[GraphEdge]]:
        nodes: list[GraphNode] = []
        node_configs: list[AllNodeTypes] = self._config.nodes

        for node_config in node_configs:
            created_node = self.BUILD_METHODS[type(node_config)](self, node_config)
            nodes.append(created_node)

        if len(set(self._config.edges)) != len(self._config.edges):
            raise ValueError("Duplicate edges found")

        edges = [GraphEdge(edge[0], edge[1]) for edge in self._config.edges]

        logger.info(f"Built graph with {len(nodes)} nodes and {len(edges)} edges")

        return nodes, edges
