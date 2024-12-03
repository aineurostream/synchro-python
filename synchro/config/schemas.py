from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import (
    AnyUrl,
    BaseModel,
    Discriminator,
    Field,
    FilePath,
    Tag,
)

from synchro.config.commons import StreamConfig

EdgeRoute = tuple[str, str]


class NodeType(str, Enum):
    INPUT_CHANNEL = "input_channel"
    OUTPUT_CHANNEL = "output_channel"
    INPUT_FILE = "input_file"
    CONVERTER_SEAMLESS = "converter_seamless"
    MIXER = "mixer"
    RESAMPLER = "resampler"
    OUTPUT_FILE = "output_file"


class BaseNodeSchema(BaseModel):
    name: Annotated[str, Field(min_length=3)]


class ChannelStreamerNodeSchema(BaseNodeSchema):
    device: int
    channel: int = 1
    stream: StreamConfig


class InputChannelStreamerNodeSchema(ChannelStreamerNodeSchema):
    node_type: Literal[NodeType.INPUT_CHANNEL] = NodeType.INPUT_CHANNEL
    chunk_size: int = 96000


class OutputChannelStreamerNodeSchema(ChannelStreamerNodeSchema):
    node_type: Literal[NodeType.OUTPUT_CHANNEL] = NodeType.OUTPUT_CHANNEL


class InputFileStreamerNodeSchema(BaseNodeSchema):
    node_type: Literal[NodeType.INPUT_FILE] = NodeType.INPUT_FILE
    path: FilePath
    stream: StreamConfig
    looping: bool = True
    delay_ms: int = 0


class SeamlessConnectorNodeSchema(BaseNodeSchema):
    node_type: Literal[NodeType.CONVERTER_SEAMLESS] = NodeType.CONVERTER_SEAMLESS
    server_url: AnyUrl
    config: dict[str, Any]
    log_file: str | None = None


class MixerNodeSchema(BaseNodeSchema):
    node_type: Literal[NodeType.MIXER] = NodeType.MIXER


class ResamplerNodeSchema(BaseNodeSchema):
    node_type: Literal[NodeType.RESAMPLER] = NodeType.RESAMPLER
    to_rate: int


class OutputFileNodeSchema(BaseNodeSchema):
    node_type: Literal[NodeType.OUTPUT_FILE] = NodeType.OUTPUT_FILE
    path: Path
    stream: StreamConfig


def get_node_discriminator_value(v: Any) -> str | None:  # noqa: ANN401
    if isinstance(v, dict):
        return v.get("node_type")
    return getattr(v, "node_type", None)


AllNodes = Annotated[
    # INPUTS
    Annotated[
        InputChannelStreamerNodeSchema,
        Tag(NodeType.INPUT_CHANNEL),
    ]
    | Annotated[InputFileStreamerNodeSchema, Tag(NodeType.INPUT_FILE)]
    |
    # CONNECTORS
    Annotated[SeamlessConnectorNodeSchema, Tag(NodeType.CONVERTER_SEAMLESS)]
    |
    # PROCESSORS
    Annotated[MixerNodeSchema, Tag(NodeType.MIXER)]
    | Annotated[ResamplerNodeSchema, Tag(NodeType.RESAMPLER)]
    |
    # OUTPUTS
    Annotated[OutputFileNodeSchema, Tag(NodeType.OUTPUT_FILE)]
    | Annotated[
        OutputChannelStreamerNodeSchema,
        Tag(NodeType.OUTPUT_CHANNEL),
    ],
    # DISCRIMINATOR
    Discriminator(get_node_discriminator_value),
]

AllNodeTypes = (
    InputChannelStreamerNodeSchema
    | InputFileStreamerNodeSchema
    | SeamlessConnectorNodeSchema
    | MixerNodeSchema
    | ResamplerNodeSchema
    | OutputFileNodeSchema
    | OutputChannelStreamerNodeSchema
)


class ProcessingGraphConfig(BaseModel):
    nodes: list[AllNodes]
    edges: list[EdgeRoute]
