import logging
import threading
from typing import Self, cast
from abc import ABC, abstractmethod

import numpy as np

from synchro.graph.graph_node import EmittingNodeMixin, GraphNode
from synchro.config.schemas import SanitizingInputConfig
from synchro.audio.frame_container import FrameContainer
from synchro.config.audio_format import AudioFormat, AudioFormatType


logger = logging.getLogger(__name__)


class AbstractInputNode(GraphNode, EmittingNodeMixin, ABC):
    """
    База для File/Channel: дети реализуют ввод, база — санитизацию.

    Требования к _pull_raw_chunk():
      • вернуть FrameContainer с «сырыми» байтами и корректным AudioFormat (INT8/16/24/32/F32),
      • frame_data может быть interleaved по каналам,
      • rate корректный.
    """

    def __init__(self, config: SanitizingInputConfig) -> None:
        super().__init__(config.name)
        self._sanitize_cfg = config
        self._buffer: FrameContainer | None = None
        self._incoming_frames = 0
        self._lock = threading.Lock()

    # Дети обязаны уметь открываться/закрываться сами (ресурсы устройства/файла)
    @abstractmethod
    def __enter__(self) -> Self: ...

    @abstractmethod
    def __exit__(self, exc_type, exc, tb): ...

    # Дети должны реализовать физическое чтение «сырых» данных
    @abstractmethod
    def _pull_raw_chunk(self) -> FrameContainer | None:
        """Вернуть очередной сырой FrameContainer или None, если данных нет сейчас."""
        ...

    # ───────── Graph API оболочка ─────────
    def put_data(self, _source: str, _data: FrameContainer) -> None:
        """Input-ноды обычно не принимают данные; оставлено для совместимости."""
        pass

    def get_data(self) -> FrameContainer | None:
        raw = self._pull_raw_chunk()
        if raw is None or len(raw.frame_data) == 0:
            return None
        return self._sanitize(raw)

    # ───────── Санитизация: bytes → float32 → (опц.) моно ─────────
    def _sanitize(self, data: FrameContainer) -> FrameContainer:
        cfg = self._sanitize_cfg
        ss = data.audio_format.sample_size  # 1/2/3/4 bytes per sample
        sr = int(data.rate)
        ch = int(data.channels) if data.channels else 1

        # 1) bytes → float32
        x = (
            _bytes_to_float32(data.frame_data, ss) 
            if cfg.enforce_float32 else 
            _bytes_passthrough_as_float_guess(data)
        )
        if cfg.verbose_logging:
            logger.info("InputSanitizer: bytes→float32 (bytes/sample=%d, size=%d)", ss, len(data.frame_data))

        # 2) моно, если нужно
        if ch > 1:
            if x.size % ch != 0:
                whole = (x.size // ch) * ch
                x = x[:whole]
            X = x.reshape(-1, ch)
            if cfg.mono_strategy == "mean":
                x = np.mean(X, axis=1, dtype=np.float32)
                if cfg.verbose_logging:
                    logger.info("InputSanitizer: downmix mono via mean over %d channels", ch)
            else:
                idx = max(0, min(cfg.select_channel_index, ch - 1))
                x = X[:, idx].astype(np.float32, copy=False)
                if cfg.verbose_logging:
                    logger.info("InputSanitizer: downmix mono via select ch=%d of %d", idx, ch)

            ch = 1
        else:
            if cfg.verbose_logging:
                logger.info("InputSanitizer: treated as mono")

        # 3) санитария/клип в диапазон
        x = np.clip(x, -1.0, 1.0).astype(np.float32)

        # 4) собрать новый контейнер с FLOAT_32 и mono
        float_fmt = AudioFormat(format_type=AudioFormatType.FLOAT_32)
        out = FrameContainer(
            audio_format=float_fmt,
            rate=sr,
            frame_data=cast(bytes, x.astype("<f4").tobytes()),
            channels=ch,
        )

        if cfg.verbose_logging:
            pk = float(np.max(np.abs(x)) + 1e-12)
            rms = float(np.sqrt(np.mean(x * x) + 1e-12))
            logger.info(
                "InputSanitizer: out float32 mono, peak=%.1f dBFS, rms=%.1f dBFS, len=%.3fs",
                20 * np.log10(pk), 20 * np.log10(rms), out.length_secs,
            )

        if not self._debug1:
            import wave
            logger.info("debug1 %s", out)
            self._debug1 = wave.open("debug_input1.wav", 'wb')
            self._debug1.setframerate(out.rate)
            self._debug1.setnchannels(out.channels)
            self._debug1.setsampwidth(2)
            
        self._debug1.writeframes(out.to_pcm16_bytes())
            
        return out


def _bytes_to_float32(raw: bytes, sample_size: int) -> np.ndarray:
    """Interleaved PCM little-endian → float32 [-1,1] (каналы пока не учитываем)."""
    if sample_size == 1:
        return np.frombuffer(raw, dtype=np.int8).astype(np.float32) / 128.0
    if sample_size == 2:
        return np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if sample_size == 3:
        a = np.frombuffer(raw, dtype=np.uint8)
        a = a[: (len(a) // 3) * 3].reshape(-1, 3)
        b = (a[:, 0].astype(np.uint32)
             | (a[:, 1].astype(np.uint32) << 8)
             | (a[:, 2].astype(np.uint32) << 16)).astype(np.int32)
        neg = (b & 0x800000) != 0
        b[neg] -= 1 << 24
        return b.astype(np.float32) / float(1 << 23)
    if sample_size == 4:
        f = np.frombuffer(raw, dtype="<f4")
        # эвристика: если «не похоже» на float32 PCM — пробуем как int32
        if np.any(np.isnan(f)) or (np.mean(np.abs(f) > 1.5) > 0.5):
            return np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
        return f.astype(np.float32)
    raise ValueError(f"Unsupported sample_size={sample_size}")


def _bytes_passthrough_as_float_guess(data: FrameContainer) -> np.ndarray:
    """
    Если вдруг решили не форсить float32 (обычно не нужно), попытка прочитать «как есть».
    Оставлено для совместимости; по умолчанию лучше всегда enforce_float32=True.
    """
    ss = data.audio_format.sample_size
    return _bytes_to_float32(data.frame_data, ss)
