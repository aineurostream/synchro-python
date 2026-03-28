import sys
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal, TextIO

from pydantic import (
    AnyUrl,
    BaseModel,
    ConfigDict,
    Discriminator,
    Field,
    FilePath,
    SerializationInfo,
    Tag,
    field_serializer,
    model_validator,
)

from synchro.config.audio_format import DEFAULT_AUDIO_FORMAT, AudioFormat

EdgeRoute = tuple[str, str]


class NodeType(StrEnum):
    INPUT_CHANNEL = "input_channel"
    OUTPUT_CHANNEL = "output_channel"
    INPUT_FILE = "input_file"
    CONVERTER_SEAMLESS = "converter_seamless"
    MIXER = "mixer"
    RESAMPLER = "resampler"
    VAD = "vad"
    NORMALIZER = "normalizer"
    DENOISER = "denoiser"
    OUTPUT_FILE = "output_file"

    PREPARER = "preparer"
    VALIDATOR = "validator"
    MEASURER = "measurer"


class BaseNodeSchema(BaseModel):
    name: Annotated[str, Field(min_length=3)]


class ChannelStreamerNodeSchema(BaseNodeSchema):
    device: int
    channel: int = 1


class InputChannelStreamerNodeSchema(ChannelStreamerNodeSchema):
    node_type: Literal[NodeType.INPUT_CHANNEL] = NodeType.INPUT_CHANNEL


class OutputChannelStreamerNodeSchema(ChannelStreamerNodeSchema):
    node_type: Literal[NodeType.OUTPUT_CHANNEL] = NodeType.OUTPUT_CHANNEL


class InputFileStreamerNodeSchema(BaseNodeSchema):
    node_type: Literal[NodeType.INPUT_FILE] = NodeType.INPUT_FILE
    path: FilePath
    looping: bool = True
    delay: float = 0


class SeamlessConnectorNodeSchema(BaseNodeSchema):
    node_type: Literal[NodeType.CONVERTER_SEAMLESS] = NodeType.CONVERTER_SEAMLESS
    server_url: AnyUrl
    lang_from: str
    lang_to: str


class MixerNodeSchema(BaseNodeSchema):
    node_type: Literal[NodeType.MIXER] = NodeType.MIXER
    min_working_step_length_secs: float = 1.0


class ResamplerNodeSchema(BaseNodeSchema):
    node_type: Literal[NodeType.RESAMPLER] = NodeType.RESAMPLER
    to_rate: int


class VadNodeSchema(BaseNodeSchema):
    node_type: Literal[NodeType.VAD] = NodeType.VAD
    threshold: int = 1000


class NormalizerNodeSchema(BaseNodeSchema):
    node_type: Literal[NodeType.NORMALIZER] = NodeType.NORMALIZER
    headroom: float = 10.0


class DenoiserNodeSchema(BaseNodeSchema):
    node_type: Literal[NodeType.DENOISER] = NodeType.DENOISER
    threshold: float = 0.5


class OutputFileNodeSchema(BaseNodeSchema):
    node_type: Literal[NodeType.OUTPUT_FILE] = NodeType.OUTPUT_FILE
    path: Path


class FormatValidatorNodeSchema(BaseNodeSchema):
    node_type: Literal[NodeType.VALIDATOR] = NodeType.VALIDATOR

    enforce_mono: bool = True
    enforce_format: AudioFormat = (
        DEFAULT_AUDIO_FORMAT  # target byte format (e.g. int16 LE)
    )
    passthrough_rate: bool = (
        True  # don't touch sample rate (resampling is a separate node)
    )


class WhisperPrepNodeSchema(BaseNodeSchema):
    """Pydantic config for a Whisper preparation node.
    Defaults to peak normalization with headroom (similar to pydub).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    node_type: Literal[NodeType.PREPARER] = NodeType.PREPARER

    # Modes for acoustics/languages (affect HPF/WPE)
    mode: Literal["default", "universal", "tonal"] = "universal"

    # Normalization: peak-headroom (default) or LUFS  # noqa: ERA001
    normalization: Literal["peak", "lufs"] = "peak"

    # For peak mode (analogous to pydub.effects.normalize):
    headroom_db: float = 10.0  # target peak = -headroom dBFS

    # For LUFS mode:
    target_lufs: float = -16.0
    lufs_block_sec: float = 0.10  # block_size for pyloudnorm (sec)
    lufs_min_sec: float = 0.10  # don't compute LUFS on shorter chunks
    gain_smooth_alpha: float = 0.25  # gain smoothing (EWMA)

    # Limiter ceiling after normalization
    true_peak_dbfs: float = -1.8

    # Dereverberation
    use_wpe: bool = True

    # No resampling inside this NODE (preserve spectrum until final stage).
    # Option kept for debugging purposes.
    resample_to_target_sr: bool = False
    target_sr: int = 16000


class TerminalMetricsDisplayNodeSchema(BaseNodeSchema):
    node_type: Literal[NodeType.MEASURER] = NodeType.MEASURER

    # TUI output destination (usually sys.stdout):
    sink: Literal["stdout", "stderr", "file"] = "stdout"
    # Terminal refresh rate (Hz)
    refresh_hz: float = 10.0
    # Metrics aggregation window length (sec)
    window_seconds: float = 4.0
    # Minimum chunk duration to include in metrics (sec)
    min_chunk_sec: float = 0.05
    # Bar height in rows (more = taller)
    bar_height: int = 10
    # Clipping threshold (for float representation)
    clip_threshold_float: float = 0.999

    # File sink settings (only used when sink="file")
    file_path: Path | None = None
    append: bool = True
    encoding: str = "utf-8"
    newline: str | None = None

    # Runtime-only field with a live file object.
    # It is excluded from serialization and type validation.
    stream: TextIO = Field(default=None, exclude=True)

    # pydantic v2: allow arbitrary types (TextIO)
    model_config = ConfigDict(arbitrary_types_allowed=True)

    @model_validator(mode="after")
    def _make_stream(
        self: "TerminalMetricsDisplayNodeSchema",
    ) -> "TerminalMetricsDisplayNodeSchema":
        """Create a real stream from config values.
        Store it in self.stream (excluded from serialization).
        """
        if self.stream is not None:
            # User already provided a ready stream manually (DI) — respect it
            return self

        if self.sink == "stdout":
            self.stream = sys.stdout
        elif self.sink == "stderr":
            self.stream = sys.stderr
        else:
            if not self.file_path:
                msg = "sink='file' requires file_path"
                raise ValueError(msg)
            mode = "a" if self.append else "w"
            # IMPORTANT: responsibility for closing the file lies with the node/context
            self.stream = self.file_path.open(
                mode,
                encoding=self.encoding,
                newline=self.newline,
            )

        return self

    # Pretty-serialize the model (e.g. for logs/configs), hiding the runtime field
    @field_serializer("file_path", check_fields=False)
    def _ser_path(self, v: Path | None, _info: SerializationInfo) -> str | None:
        return str(v) if v else None


def get_node_discriminator_value(v: dict[str, object] | object) -> str | None:
    if isinstance(v, dict):
        node_type = v.get("node_type")
        return node_type if isinstance(node_type, str) else None
    node_type = getattr(v, "node_type", None)
    return node_type if isinstance(node_type, str) else None


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
    | Annotated[VadNodeSchema, Tag(NodeType.VAD)]
    | Annotated[NormalizerNodeSchema, Tag(NodeType.NORMALIZER)]
    | Annotated[DenoiserNodeSchema, Tag(NodeType.DENOISER)]
    | Annotated[FormatValidatorNodeSchema, Tag(NodeType.VALIDATOR)]
    | Annotated[WhisperPrepNodeSchema, Tag(NodeType.PREPARER)]
    |
    # OUTPUTS
    Annotated[OutputFileNodeSchema, Tag(NodeType.OUTPUT_FILE)]
    | Annotated[OutputChannelStreamerNodeSchema, Tag(NodeType.OUTPUT_CHANNEL)]
    | Annotated[TerminalMetricsDisplayNodeSchema, Tag(NodeType.MEASURER)],
    # DISCRIMINATOR
    Discriminator(get_node_discriminator_value),
]

AllNodeTypes = (
    InputChannelStreamerNodeSchema
    | InputFileStreamerNodeSchema
    | SeamlessConnectorNodeSchema
    | MixerNodeSchema
    | ResamplerNodeSchema
    | VadNodeSchema
    | NormalizerNodeSchema
    | DenoiserNodeSchema
    | OutputFileNodeSchema
    | OutputChannelStreamerNodeSchema
    | FormatValidatorNodeSchema
    | WhisperPrepNodeSchema
    | TerminalMetricsDisplayNodeSchema
)


class ProcessingGraphConfig(BaseModel):
    nodes: list[AllNodes]
    edges: list[EdgeRoute]
