import logging

from synchro.audio.audio_device_manager import AudioDeviceManager
from synchro.config.schemas import (
    AllNodeTypes,
    InputChannelStreamerNodeSchema,
    InputFileStreamerNodeSchema,
    MixerNodeSchema,
    OutputChannelStreamerNodeSchema,
    OutputFileNodeSchema,
    ProcessingGraphConfig,
    ResamplerNodeSchema,
    SeamlessConnectorNodeSchema,
)
from synchro.graph.graph_edge import GraphEdge
from synchro.graph.graph_node import GraphNode
from synchro.graph.nodes.inputs.channel_input_node import ChannelInputNode
from synchro.graph.nodes.inputs.file_input_node import FileInputNode
from synchro.graph.nodes.models.seamless_connector_node import SeamlessConnectorNode
from synchro.graph.nodes.outputs.channel_output_node import ChannelOutputNode
from synchro.graph.nodes.outputs.file_output_node import FileOutputNode
from synchro.graph.nodes.processors.mixer_node import MixerNode
from synchro.graph.nodes.processors.resample_node import ResampleNode

logger = logging.getLogger(__name__)


class GraphInitializer:
    def __init__(
        self,
        config: ProcessingGraphConfig,
        manager: AudioDeviceManager,
    ) -> None:
        self._config = config
        self._manager = manager

    def _create_channel_input_node(
        self,
        config: InputChannelStreamerNodeSchema,
    ) -> ChannelInputNode:
        return ChannelInputNode(config, self._manager)

    def _create_file_input_node(
        self,
        config: InputFileStreamerNodeSchema,
    ) -> FileInputNode:
        return FileInputNode(config)

    def _create_channel_output_node(
        self,
        config: OutputChannelStreamerNodeSchema,
    ) -> ChannelOutputNode:
        return ChannelOutputNode(config, self._manager)

    def _create_file_output_node(
        self,
        config: OutputFileNodeSchema,
    ) -> FileOutputNode:
        return FileOutputNode(config)

    def _create_seamless_connector_node(
        self,
        config: SeamlessConnectorNodeSchema,
    ) -> SeamlessConnectorNode:
        return SeamlessConnectorNode(config)

    def _create_mixer_node(self, config: MixerNodeSchema) -> MixerNode:
        return MixerNode(config)

    def _create_resample_node(self, config: ResamplerNodeSchema) -> ResampleNode:
        return ResampleNode(config)

    def build(self) -> tuple[list[GraphNode], list[GraphEdge]]:
        nodes: list[GraphNode] = []
        node_configs: list[AllNodeTypes] = self._config.nodes

        for node_config in node_configs:
            if isinstance(node_config, InputChannelStreamerNodeSchema):
                nodes.append(self._create_channel_input_node(node_config))
            if isinstance(node_config, InputFileStreamerNodeSchema):
                nodes.append(self._create_file_input_node(node_config))
            elif isinstance(node_config, OutputChannelStreamerNodeSchema):
                nodes.append(self._create_channel_output_node(node_config))
            elif isinstance(node_config, OutputFileNodeSchema):
                nodes.append(self._create_file_output_node(node_config))
            elif isinstance(node_config, SeamlessConnectorNodeSchema):
                nodes.append(self._create_seamless_connector_node(node_config))
            elif isinstance(node_config, MixerNodeSchema):
                nodes.append(self._create_mixer_node(node_config))
            elif isinstance(node_config, ResamplerNodeSchema):
                nodes.append(self._create_resample_node(node_config))
            else:
                raise TypeError(f"Unknown node type: {node_config}")

        if len(set(self._config.edges)) != len(self._config.edges):
            raise ValueError("Duplicate edges found")

        edges = [GraphEdge(edge[0], edge[1]) for edge in self._config.edges]

        logger.info(f"Built graph with {len(nodes)} nodes and {len(edges)} edges")

        return nodes, edges
