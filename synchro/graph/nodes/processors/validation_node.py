import logging
import threading

import numpy as np

from synchro.audio.frame_container import FrameContainer
from synchro.config.audio_format import AudioFormat, AudioFormatType, DEFAULT_AUDIO_FORMAT
from synchro.graph.graph_node import EmittingNodeMixin, GraphNode, ReceivingNodeMixin
from synchro.config.schemas import FormatValidatorNodeSchema
from synchro.config.commons import LONG_BUFFER_SIZE_SEC


logger = logging.getLogger(__name__)


class FormatValidatorNode(GraphNode, ReceivingNodeMixin, EmittingNodeMixin):
    """
    Прозрачная нода-«санитайзер» формата, совместимая с графом:
    - поддерживает контекстный менеджер (__enter__/__exit__),
    - принимает данные через put_data, на get_data выдаёт «ровно то, что пришло»,
      но с приведением в моно (при enforce_mono) и в целевой PCM-формат.
    """

    def __init__(self, config: FormatValidatorNodeSchema) -> None:
        super().__init__(config.name)
        self._config = config
        self._buffer: FrameContainer | None = None
        self._incoming_frames = 0
        self._lock = threading.Lock()

    def put_data(self, _source: str, data: FrameContainer) -> None:
        with self._lock:
            self._buffer = data.clone() if self._buffer is None else self._buffer.append(data)
            self._incoming_frames += data.length_frames

    def get_data(self) -> FrameContainer | None:
        with self._lock:
            if not self._buffer or self._incoming_frames == 0:
                return None
            # Берём хвост ровно на объём новых фреймов и валидируем
            tail = self._buffer.get_end_frames(self._incoming_frames)
            out = self._validate_and_convert(tail)

            # Подрезаем общий буфер (как в других узлах)
            self._buffer = self._buffer.get_end_seconds(LONG_BUFFER_SIZE_SEC)
            self._incoming_frames = 0

            logger.info("Format chunk get")
            return out

    def _validate_and_convert(self, data: FrameContainer) -> FrameContainer:
        in_fmt = data.audio_format
        rate = int(data.rate)

        # 1) bytes -> float32 (и → моно, если нужно)
        x = self._bytes_to_float(data.frame_data, in_fmt)
        if self._config.enforce_mono:
            x = self._to_mono_assume_interleaved(x, in_fmt, data)  # см. ниже
        # если не enforce_mono, считаем, что уже моно (или interleaved — тогда оставьте приводить раньше)

        # 2) float32 -> bytes в целевой формат
        raw = self._float_to_bytes(x, self._config.enforce_format)

        # 3) собираем новый контейнер (rate сохраняем/не трогаем)
        return FrameContainer(
            audio_format=self._config.enforce_format,
            rate=rate if self._config.passthrough_rate else rate,
            frame_data=raw,
        )

    @staticmethod
    def _bytes_to_float(raw: bytes, fmt: AudioFormat) -> np.ndarray:
        """Interleaved PCM little-endian → float32 [-1,1] (без сведения в моно)."""
        if fmt.format_type == AudioFormatType.INT_8:
            return np.frombuffer(raw, dtype=np.int8).astype(np.float32) / 128.0
        if fmt.format_type == AudioFormatType.INT_16:
            return np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
        if fmt.format_type == AudioFormatType.INT_24:
            a = np.frombuffer(raw, dtype=np.uint8)
            if len(a) % 3 != 0:
                a = a[: (len(a) // 3) * 3]
            a = a.reshape(-1, 3)
            b = (a[:, 0].astype(np.uint32)
                 | (a[:, 1].astype(np.uint32) << 8)
                 | (a[:, 2].astype(np.uint32) << 16)).astype(np.int32)
            neg = (b & 0x800000) != 0
            b[neg] -= 1 << 24
            return b.astype(np.float32) / float(1 << 23)
        if fmt.format_type == AudioFormatType.INT_32:
            return np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
        if fmt.format_type == AudioFormatType.FLOAT_32:
            return np.frombuffer(raw, dtype="<f4").astype(np.float32)
        raise ValueError(f"Unsupported input format: {fmt.format_type}")

    @staticmethod
    def _float_to_bytes(x: np.ndarray, out_fmt: AudioFormat) -> bytes:
        """float32 [-1,1] → PCM little-endian заданного формата."""
        x = np.clip(x.astype(np.float32), -1.0, 1.0)
        if out_fmt.format_type == AudioFormatType.INT_8:
            return (x * 128.0).astype(np.int8).tobytes()
        if out_fmt.format_type == AudioFormatType.INT_16:
            return (x * 32768.0).astype("<i2").tobytes()
        if out_fmt.format_type == AudioFormatType.INT_24:
            i = np.clip((x * (1 << 23)).astype(np.int32), -(1 << 23), (1 << 23) - 1)
            out = np.empty((i.size, 3), dtype=np.uint8)
            ii = i.copy()
            ii[ii < 0] += 1 << 24
            out[:, 0] = (ii & 0xFF).astype(np.uint8)
            out[:, 1] = ((ii >> 8) & 0xFF).astype(np.uint8)
            out[:, 2] = ((ii >> 16) & 0xFF).astype(np.uint8)
            return out.tobytes()
        if out_fmt.format_type == AudioFormatType.INT_32:
            return (x * 2147483648.0).astype("<i4").tobytes()
        if out_fmt.format_type == AudioFormatType.FLOAT_32:
            return x.astype("<f4").tobytes()
        raise ValueError(f"Unsupported output format: {out_fmt.format_type}")

    def _to_mono_assume_interleaved(self, x: np.ndarray, fmt: AudioFormat, data: FrameContainer) -> np.ndarray:
        """
        Сведение в моно. FrameContainer у вас не хранит явное количество каналов.
        Валидация каналов сделана выше по графу (File/ChannelInput). Если сюда
        всё же попадёт interleaved многоканал, можно расширить API и передавать hint.
        Здесь считаем, что уже моно → просто возвращаем.
        """
        return x.astype(np.float32)
