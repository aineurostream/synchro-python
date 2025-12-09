from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Literal, TextIO, cast

from pydantic import (
    AnyUrl,
    BaseModel,
    Discriminator,
    Field,
    FilePath,
    Tag,
    ConfigDict,
    model_validator,
    field_serializer,
)

from synchro.config.audio_format import AudioFormat
from synchro.config.audio_format import DEFAULT_AUDIO_FORMAT


EdgeRoute = tuple[str, str]


class NodeType(str, Enum):
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
    enforce_format: AudioFormat = DEFAULT_AUDIO_FORMAT  # во что приводить байты (например, int16 LE)
    passthrough_rate: bool = True  # частоту не трогаем (ресэмпл — отдельной нодой)


class WhisperPrepNodeSchema(BaseNodeSchema):
    """
    Pydantic-конфиг для ноды подготовки под Whisper.
    По умолчанию — безопасная peak-нормализация с headroom (как в pydub).
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # тип ноды, если у тебя в базовом конфиге это требуется:
    # node_type: Literal[NodeType.PREPARATION] = NodeType.PREPARATION

    name: str

    # Режимы под акустику/языки (влияют на HPF/WPE)
    mode: Literal["default", "universal", "tonal"] = "universal"

    # Нормализация: peak-headroom (дефолт) или LUFS
    normalization: Literal["peak", "lufs"] = "peak"

    # Для peak-режима (аналог pydub.effects.normalize):
    headroom_db: float = 10.0  # целевой пик = −headroom dBFS

    # Для LUFS-режима:
    target_lufs: float = -16.0
    lufs_block_sec: float = 0.10     # block_size для pyloudnorm (сек)
    lufs_min_sec: float = 0.10       # не считаем LUFS на более коротких чанках
    gain_smooth_alpha: float = 0.25  # сглаживание усиления (EWMA)

    # Лимитер-потолок после нормализации
    true_peak_dbfs: float = -1.8

    # Дереверберация
    use_wpe: bool = True

    # Ресэмпл внутри НОДЫ не делаем (держим спектр до финала); опция оставлена на случай отладки
    resample_to_target_sr: bool = False
    target_sr: int = 16000


class TerminalMetricsDisplayNodeSchema(BaseNodeSchema):
    node_type: Literal[NodeType.MEASURER] = NodeType.MEASURER

    # Куда печатаем TUI (обычно sys.stdout):
    sink: Literal["stdout", "stderr", "file"] = "stdout"
    # Как часто перерисовывать терминал (Гц)
    refresh_hz: float = 10.0
    # Длина окна агрегации метрик (сек)
    window_seconds: float = 4.0
    # Минимальная длительность чанка, чтобы учитывать метрики (сек)
    min_chunk_sec: float = 0.05
    # Высота «столбиков» в строках (чем больше, тем выше)
    bar_height: int = 10
    # Порог клиппинга (для float-представления)
    clip_threshold_float: float = 0.999

    # --- Runtime-поле: реальный объект файла (НЕ сериализуем, НЕ валидируем как тип pydantic) ---
    stream: TextIO = Field(default=None, exclude=True)

    # pydantic v2: разрешаем произвольные типы (TextIO)
    model_config = ConfigDict(arbitrary_types_allowed=True)

    @model_validator(mode="after")
    def _make_stream(self: "TerminalMetricsDisplayNodeSchema") -> "TerminalMetricsDisplayNodeSchema":
        """
        Создаём реальный поток из спецификации.
        Прячем его в self.stream (он исключён из сериализации).
        """
        if self.stream is not None:
            # Пользователь уже положил готовый поток вручную (DI) — уважаем
            return self

        if self.sink == "stdout":
            self.stream = sys.stdout
        elif self.sink == "stderr":
            self.stream = sys.stderr
        else:
            if not self.file_path:
                raise ValueError("sink='file' требует file_path")
            mode = "a" if self.append else "w"
            # ВАЖНО: ответственность за закрытие файла на стороне ноды/контекста
            self.stream = open(self.file_path, mode, encoding=self.encoding, newline=self.newline)

        return self

    # Красиво сериализуем модель (например, в логи/конфиги), пряча runtime-поле
    @field_serializer("file_path", check_fields=False)
    def _ser_path(self, v: Path | None, _info):
        return str(v) if v else None
    

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
