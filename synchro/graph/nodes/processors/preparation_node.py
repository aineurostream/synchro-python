import logging
from types import TracebackType
from typing import Literal, Self, cast

import numpy as np
from scipy.signal import butter, filtfilt

from synchro.audio.frame_container import FrameContainer
from synchro.config.commons import LONG_BUFFER_SIZE_SEC
from synchro.config.schemas import WhisperPrepNodeSchema
from synchro.graph.graph_node import EmittingNodeMixin, GraphNode, ReceivingNodeMixin

logger = logging.getLogger(__name__)

PCM_16_BYTES = 2
PCM_24_BYTES = 3
PCM_32_BYTES = 4
WAV_FLOAT_THRESHOLD = 1.5
INT_DETECTION_THRESHOLD = 0.5
SIGNAL_PEAK_LIMIT = 0.999

# ─────────────────────────────(опциональный WPE)──────────────────────────────
# WPE = Weighted Prediction Error. Бережная «дереверберация».
# Если pyroomacoustics не установлен — шаг тихо пропускаем.
try:
    import pyroomacoustics  # noqa: F401

    _HAS_PRA = True
except ImportError:  # pragma: no cover
    _HAS_PRA = False


# ───────────────────────────── нода ─────────────────────────────
class WhisperPrepNode(GraphNode, ReceivingNodeMixin, EmittingNodeMixin):
    """1) bytes -> float32, сразу моно
    2) нормализация: peak(headroom) [дефолт] или LUFS (безопасно для коротких чанков)
    3) мягкий лимитер (true peak)
    4) (опц.) WPE dereverb
    5) HPF/LPF (zero-phase)
    6) float32 -> bytes (исходная разрядность), SR не меняем.
    """

    def __init__(self, config: WhisperPrepNodeSchema) -> None:
        super().__init__(config.name)
        self._config = config
        self._buffer: FrameContainer | None = None
        self._incoming_frames = 0
        self._last_gain_db: float | None = None  # для LUFS-сглаживания

        self._presets = {
            "default": {
                "hpf": 120.0,
                "lpf_ratio": 0.975,
                "wpe_taps": 10,
                "wpe_delay": 3,
                "wpe_iters": 3,
            },
            "universal": {
                "hpf": 65.0,
                "lpf_ratio": 0.975,
                "wpe_taps": 9,
                "wpe_delay": 3,
                "wpe_iters": 3,
            },
            "tonal": {
                "hpf": 55.0,
                "lpf_ratio": 0.975,
                "wpe_taps": 8,
                "wpe_delay": 3,
                "wpe_iters": 2,
            },
        }
        if self._config.mode not in self._presets:
            logger.warning(
                "Unknown mode '%s', fallback to 'universal'",
                self._config.mode,
            )
            self._config.mode = "universal"

    # Контекстный менеджер (граф любит with node)
    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> Literal[False]:
        self._buffer = None
        self._incoming_frames = 0
        return False

    # Graph API
    def put_data(self, _source: str, data: FrameContainer) -> None:
        self._buffer = (
            data.clone() if self._buffer is None else self._buffer.append(data)
        )
        self._incoming_frames += data.length_frames

    def get_data(self) -> FrameContainer | None:
        if not self._buffer or self._incoming_frames == 0:
            return None
        processed = self._process_buffer(self._buffer).get_end_frames(
            self._incoming_frames,
        )
        self._buffer = self._buffer.get_end_seconds(LONG_BUFFER_SIZE_SEC)
        self._incoming_frames = 0
        return processed

    # ядро
    def _process_buffer(self, buffer: FrameContainer) -> FrameContainer:
        sample_size = buffer.audio_format.sample_size
        rate_in = int(buffer.rate)

        # 1) bytes -> float32 моно
        x = _pcm_bytes_to_float32_mono(buffer.frame_data, sample_size)

        # 2) SR — держим как есть (по умолчанию)
        target_sr = (
            rate_in
            if not self._config.resample_to_target_sr
            else self._config.target_sr
        )
        y = _resample_if_needed(x, rate_in, target_sr)

        # 3) Нормализация (peak-headroom по умолчанию, как в pydub)
        if self._config.normalization == "peak":
            y = _normalize_peak_headroom(y, headroom_db=self._config.headroom_db)
        else:
            y, _ = self._safe_lufs_normalize(y, sr=target_sr)

        # лимитер-потолок
        y = _soft_limiter_tanh(y, self._config.true_peak_dbfs)

        # 4) Dereverb (опционально)
        p = self._presets[self._config.mode]
        if self._config.use_wpe and _HAS_PRA:
            y = _wpe_dereverb(
                y,
                target_sr,
                int(p["wpe_taps"]),
                int(p["wpe_delay"]),
                int(p["wpe_iters"]),
            )
            y = _soft_limiter_tanh(
                y,
                self._config.true_peak_dbfs,
            )  # поджать возможный всплеск
        elif self._config.use_wpe and not _HAS_PRA:
            logger.debug("pyroomacoustics not available, skipping WPE")

        # 5) Фильтры HPF/LPF (zero-phase)
        lpf_hz = _safe_lpf_hz(target_sr, p["lpf_ratio"])
        y = _butter_zero_phase(y, sr=target_sr, f_low=p["hpf"], f_high=lpf_hz, order=4)

        # 6) Санитария + обратная конверсия
        y = np.nan_to_num(y, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
        pk = float(np.max(np.abs(y)) + 1e-12)
        if pk > SIGNAL_PEAK_LIMIT:
            y *= SIGNAL_PEAK_LIMIT / pk

        out_rate = target_sr
        raw = _float32_to_pcm_bytes(y, sample_size)

        if self._config.resample_to_target_sr and out_rate != rate_in:
            try:
                return FrameContainer.from_params(  # type: ignore[attr-defined]
                    rate=out_rate,
                    audio_format=buffer.audio_format,
                    channels=1,
                    frame_data=cast("bytes", raw),
                )
            except (AttributeError, TypeError, ValueError) as e:
                logger.warning(
                    "Cannot build FrameContainer with new rate (%s). "
                    "Fallback to original. Err: %s",
                    out_rate,
                    e,
                )

        return FrameContainer.from_config(buffer, cast("bytes", raw))

    # безопасная LUFS-нормализация (не падает на коротких чанках)
    def _safe_lufs_normalize(
        self,
        x: np.ndarray,
        sr: int,
    ) -> tuple[np.ndarray, float]:
        target_lufs = self._config.target_lufs
        block_sec = self._config.lufs_block_sec
        min_sec = self._config.lufs_min_sec
        smooth_alpha = self._config.gain_smooth_alpha
        try:
            import pyloudnorm as pyln  # noqa: PLC0415

            have_pyloud = True
        except ImportError:
            have_pyloud = False

        n = len(x)
        if n == 0 or sr <= 0:
            return x.astype(np.float32), 0.0

        # Если нет pyloudnorm — fallback к RMS
        if not have_pyloud:
            cur_rms_db = _rms_dbfs(x)
            gain_db = target_lufs - cur_rms_db
            g = _smooth_gain(self._last_gain_db, gain_db, smooth_alpha)
            self._last_gain_db = g
            return _apply_gain_db(x, g), g

        min_samples = max(1, int(sr * min_sec))
        block_size = max(1, int(sr * block_sec))

        if n >= min_samples:
            try:
                meter = pyln.Meter(sr, block_size=block_size)
                lufs = float(meter.integrated_loudness(x.astype(np.float64)))
                gain_db = target_lufs - lufs
            except (RuntimeError, ValueError, FloatingPointError):
                cur_rms_db = _rms_dbfs(x)
                gain_db = target_lufs - cur_rms_db
        # слишком коротко — используем прошлый гейн, либо RMS-оценку
        elif self._last_gain_db is not None:
            gain_db = self._last_gain_db
        else:
            cur_rms_db = _rms_dbfs(x)
            gain_db = target_lufs - cur_rms_db

        g = _smooth_gain(self._last_gain_db, gain_db, smooth_alpha)
        self._last_gain_db = g
        return _apply_gain_db(x, g), g


# ─────────────────────────── вспом. DSP ───────────────────────────
def _pcm_bytes_to_float32_mono(raw: bytes, sample_size: int) -> np.ndarray:
    """Interleaved PCM little-endian -> float32 [-1,1] (assume mono input)."""
    if sample_size == 1:
        return np.clip(
            np.frombuffer(raw, dtype=np.int8).astype(np.float32) / 128.0,
            -1.0,
            1.0,
        )
    if sample_size == PCM_16_BYTES:
        return np.clip(
            np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0,
            -1.0,
            1.0,
        )
    if sample_size == PCM_24_BYTES:
        a = np.frombuffer(raw, dtype=np.uint8)
        if len(a) % 3 != 0:
            a = a[: (len(a) // 3) * 3]
        a = a.reshape(-1, 3)
        b = (
            a[:, 0].astype(np.uint32)
            | (a[:, 1].astype(np.uint32) << 8)
            | (a[:, 2].astype(np.uint32) << 16)
        ).astype(np.int32)
        neg = (b & 0x800000) != 0
        b[neg] -= 1 << 24
        x = b.astype(np.float32) / float(1 << 23)
        return np.clip(x, -1.0, 1.0)
    if sample_size == PCM_32_BYTES:
        f = np.frombuffer(raw, dtype="<f4")
        if np.any(np.isnan(f)) or (
            np.mean(np.abs(f) > WAV_FLOAT_THRESHOLD) > INT_DETECTION_THRESHOLD
        ):
            i = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
            return np.clip(i, -1.0, 1.0)
        return np.clip(f.astype(np.float32), -1.0, 1.0)
    msg = f"Unsupported sample_size={sample_size}"
    raise ValueError(msg)


def _float32_to_pcm_bytes(x: np.ndarray, sample_size: int) -> bytes:
    x = np.clip(x.astype(np.float32), -1.0, 1.0)
    if sample_size == 1:
        return (x * 128.0).astype(np.int8).tobytes()
    if sample_size == PCM_16_BYTES:
        return (x * 32768.0).astype("<i2").tobytes()
    if sample_size == PCM_24_BYTES:
        i = np.clip((x * (1 << 23)).astype(np.int32), -(1 << 23), (1 << 23) - 1)
        out = np.empty((i.size, 3), dtype=np.uint8)
        ii = i.copy()
        ii[ii < 0] += 1 << 24
        out[:, 0] = (ii & 0xFF).astype(np.uint8)
        out[:, 1] = ((ii >> 8) & 0xFF).astype(np.uint8)
        out[:, 2] = ((ii >> 16) & 0xFF).astype(np.uint8)
        return out.tobytes()
    if sample_size == PCM_32_BYTES:
        return x.astype("<f4").tobytes()
    msg = f"Unsupported sample_size={sample_size}"
    raise ValueError(msg)


def _resample_if_needed(x: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    if sr_in == sr_out:
        return x.astype(np.float32)
    import librosa  # noqa: PLC0415

    return librosa.resample(
        x.astype(np.float32),
        orig_sr=sr_in,
        target_sr=sr_out,
        res_type="kaiser_best",
    ).astype(np.float32)


def _normalize_peak_headroom(x: np.ndarray, headroom_db: float) -> np.ndarray:
    """Peak-нормализация «как в pydub.effects.normalize(headroom=H)»:
    делаем так, чтобы абсолютный пик стал равен -H dBFS.
    """
    peak = float(np.max(np.abs(x)) + 1e-12)
    if peak == 0.0:
        return x.astype(np.float32)
    target_peak = 10.0 ** (-headroom_db / 20.0)  # линейная цель
    gain = target_peak / peak
    return (x * gain).astype(np.float32)


def _soft_limiter_tanh(x: np.ndarray, ceiling_dbfs: float) -> np.ndarray:
    ceiling = 10.0 ** (ceiling_dbfs / 20.0)
    peak = float(np.max(np.abs(x)) + 1e-12)
    if peak <= ceiling:
        return x.astype(np.float32)
    y = np.tanh(2.0 * (x / peak))
    y = y / (np.max(np.abs(y)) + 1e-12) * ceiling
    return y.astype(np.float32)


def _wpe_dereverb(
    x: np.ndarray,
    _sr: int,
    taps: int,
    delay: int,
    iterations: int,
) -> np.ndarray:
    """Безопасный вызов WPE-дереверберации для любых версий pyroomacoustics.
    При отсутствии модуля — возвращает входной сигнал без изменений.
    """
    try:
        import pyroomacoustics as pra  # noqa: PLC0415

        # 🔹 Новый API (>=0.7): функция в подмодуле
        try:
            from pyroomacoustics.dereverberation import wpe as pra_wpe  # noqa: PLC0415
        except ImportError:
            pra_wpe = None

        frame_len, hop = 512, 128
        window = np.hanning(frame_len).astype(np.float32)

        stft = pra.transform.STFT(frame_len, hop=hop, analysis_window=window)
        x_spectrum = stft.analysis(x.astype(np.float32))
        x_spectrum_arr = x_spectrum.T[..., np.newaxis]

        if pra_wpe is not None:
            y_spectrum = pra_wpe.wpe(
                x_spectrum_arr,
                taps=taps,
                delay=delay,
                iterations=iterations,
            )
        elif hasattr(pra, "dereverberation") and hasattr(pra.dereverberation, "wpe"):
            # старый API (<0.7)
            y_spectrum = pra.dereverberation.wpe(
                x_spectrum_arr,
                taps=taps,
                delay=delay,
                iterations=iterations,
            )
        else:
            # модуль недоступен
            return x

        y_frames = y_spectrum[..., 0].T
        istft = pra.transform.STFT(frame_len, hop=hop, synthesis_window=window)
        y = istft.synthesis(y_frames.T)
        return y[: len(x)].astype(np.float32)

    except (
        AttributeError,
        FloatingPointError,
        ImportError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as e:
        logger.debug("WPE dereverb skipped: %s", e)
        return x


def _butter_zero_phase(
    x: np.ndarray,
    sr: int,
    f_low: float | None,
    f_high: float | None,
    order: int = 4,
) -> np.ndarray:
    y = x.astype(np.float32)
    nyq = 0.5 * sr
    if f_low is not None and f_low > 0:
        wn = float(max(1e-6, min(0.999999, f_low / nyq)))
        b, a = butter(order, wn, btype="highpass")
        y = filtfilt(b, a, y).astype(np.float32)
    if f_high is not None and f_high < nyq:
        wn = float(max(1e-6, min(0.999999, f_high / nyq)))
        b, a = butter(order, wn, btype="lowpass")
        y = filtfilt(b, a, y).astype(np.float32)
    return y.astype(np.float32)


def _safe_lpf_hz(sr: int, lpf_ratio: float) -> float:
    nyq = 0.5 * sr
    lpf = min(lpf_ratio * nyq, nyq - 200.0)
    return float(max(1000.0, lpf))


def _rms_dbfs(x: np.ndarray) -> float:
    rms = float(np.sqrt(np.mean(np.square(x)) + 1e-12))
    return 20.0 * np.log10(max(rms, 1e-12))


def _apply_gain_db(x: np.ndarray, gain_db: float) -> np.ndarray:
    return (x * (10.0 ** (gain_db / 20.0))).astype(np.float32)


def _smooth_gain(prev_db: float | None, cur_db: float, alpha: float) -> float:
    """EWMA по усилению (в dB), чтобы не «дышало»."""
    a = float(np.clip(alpha, 0.0, 1.0))
    if prev_db is None:
        return cur_db
    return (1.0 - a) * prev_db + a * cur_db
