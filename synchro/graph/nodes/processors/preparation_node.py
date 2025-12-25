import threading
import logging
from dataclasses import dataclass
from typing import Optional, Tuple, Union, cast

try:
    import torch
    from denoiser import pretrained
    from denoiser.dsp import convert_audio
except Exception:
    torch = None

import numpy as np
from scipy.signal import stft, istft, butter, filtfilt

from synchro.audio.online_wpe import OnlineWPEProcessor
from synchro.audio.frame_container import FrameContainer
from synchro.config.commons import LONG_BUFFER_SIZE_SEC
from synchro.graph.graph_node import EmittingNodeMixin, GraphNode, ReceivingNodeMixin
from synchro.config.schemas import WhisperPrepNodeSchema

logger = logging.getLogger(__name__)

# ─────────────────────────────(опциональный WPE)──────────────────────────────
# WPE = Weighted Prediction Error. Бережная «дереверберация».
# Если pyroomacoustics не установлен — шаг тихо пропускаем.
try:
    import pyroomacoustics as pra
    _HAS_PRA = True
except Exception:  # pragma: no cover
    _HAS_PRA = False
    

# ───────────────────────────── нода ─────────────────────────────
import logging
from typing import Literal, Optional, cast

import numpy as np
from pydantic import BaseModel, ConfigDict
from scipy.signal import butter, filtfilt

from synchro.audio.frame_container import FrameContainer
from synchro.config.commons import LONG_BUFFER_SIZE_SEC
from synchro.graph.graph_node import EmittingNodeMixin, GraphNode, ReceivingNodeMixin

logger = logging.getLogger(__name__)


# ──────────────────────── ЧИСТЫЕ ФУНКЦИИ ОБРАБОТКИ ───────────────────────────
def normalize_peak_headroom(x: np.ndarray, headroom_db: float) -> np.ndarray:
    """
    ЗАЧЕМ: привести сигнал к опорному уровню так, чтобы САМЫЙ ВЫСОКИЙ пик
    оказался на уровне −headroom dBFS. Это стабилизирует «громкость» спектрограмм,
    уменьшает «плавание» сегментаций в ASR.

    ЭФФЕКТ: линейный масштаб по всему сигналу (никаких артефактов), пик после шага
    ≈ 10^(-headroom_db/20). Типичные headroom: 6..12 dB.

    ВХОД/ВЫХОД: float32 в диапазоне примерно [-1, 1].
    """
    logger.info("Normalizing peak to −%.1f dBFS", headroom_db)
    peak = float(np.max(np.abs(x)) + 1e-12)
    if peak == 0.0:
        return x
    target_peak_lin = 10.0 ** (-headroom_db / 20.0)
    gain = target_peak_lin / peak
    return (x * gain).astype(np.float32)


def soft_limit_tanh(x: np.ndarray, ceiling_dbfs: float) -> np.ndarray:
    """
    ЗАЧЕМ: аккуратно «подрезать» редкие сверхпики, не внося жёсткой
    гармонической дисторсии как при клиппинге.

    ЭФФЕКТ: гладкое сжатие вершин (через tanh) к потолку 10^(ceiling/20).
    Типичный потолок: −2..−1 dBFS — достаточно для безопасности кодека/энкодера.

    ВХОД/ВЫХОД: float32; при отсутствии пиков выше потолка — сигнал возвращается как есть.
    """
    logger.info("Applying soft limiter with ceiling at %.1f dBFS", ceiling_dbfs)
    ceiling = 10.0 ** (ceiling_dbfs / 20.0)
    peak = float(np.max(np.abs(x)) + 1e-12)
    if peak <= ceiling:
        return x.astype(np.float32)
    y = x / peak
    y = np.tanh(2.0 * y)
    y = y / (np.max(np.abs(y)) + 1e-12) * ceiling
    return y.astype(np.float32)


def apply_filters_zero_phase(
    x: np.ndarray,
    sr: int,
    f_low: Optional[float],
    lpf_ratio_to_nyq: float,
    order: int = 4,
) -> np.ndarray:
    """
    ЗАЧЕМ: убрать гул/инфраниз (HPF) и «мусор» на высоких (LPF) без фазовых сдвигов.
    Нулевая фаза (filtfilt) → форма огибающих речи сохраняется.

    ЭФФЕКТ:
      • HPF 50..120 Гц: подавляет гул/шумы кондиционеров/удары по стойке.
      • LPF 0.95..0.99 Найквиста: «чистит» бесполезную кромку частот для ASR.

    ВХОД/ВЫХОД: float32, SR не меняется.
    """
    logger.info("Applying zero-phase filters: HPF=%s, LPF ratio=%.4f, order=%d",
        f"{f_low:.1f} Hz" if (f_low and f_low > 0) else "off",
        lpf_ratio_to_nyq,
        order,
    )

    y = x.astype(np.float32)
    nyq = 0.5 * sr
    # LPF частота — доля от Найквиста, но не ближе 200 Гц к нему и не ниже 1 кГц
    f_high = min(max(0.0, lpf_ratio_to_nyq) * nyq, nyq - 200.0)
    f_high = float(max(1000.0, f_high))

    if f_low is not None and f_low > 0:
        wn = float(max(1e-6, min(0.999999, f_low / nyq)))
        b, a = butter(order, wn, btype="highpass")
        y = filtfilt(b, a, y).astype(np.float32)

    if f_high < nyq:
        wn = float(max(1e-6, min(0.999999, f_high / nyq)))
        b, a = butter(order, wn, btype="lowpass")
        y = filtfilt(b, a, y).astype(np.float32)

    return y


def sanitize_and_safety(x: np.ndarray, final_peak_cap: float = 0.999) -> np.ndarray:
    """
    ЗАЧЕМ: защититься от NaN/Inf и редких перепиков после цепочки.
    ЭФФЕКТ: заменяем NaN/Inf на 0, при необходимости масштабируем на пару десятых дБ.
    """
    logger.info("Applying sanitize and safety with final peak cap at %.3f", final_peak_cap)

    y = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
    pk = float(np.max(np.abs(y)) + 1e-12)
    if pk > final_peak_cap:
        y *= (final_peak_cap / pk)
    return y


def peak_dbfs(x: np.ndarray) -> float:
    """Удобный helper для логов: пиковый уровень в dBFS."""
    pk = float(np.max(np.abs(x)) + 1e-12)
    return 20.0 * np.log10(pk)


# ───────────────────────────── НОДА ГРАФА ────────────────────────────────────
class WhisperPrepNode(GraphNode, ReceivingNodeMixin, EmittingNodeMixin):
    """
    """

    def __init__(self, config: WhisperPrepNodeSchema) -> None:
        super().__init__(config.name)
        self._config = config
        self._buffer: FrameContainer | None = None
        self._incoming_frames = 0
        self._lock = threading.Lock()

        # внутренний float32-аккумулятор и текущая частота
        self._accum: Optional[np.ndarray] = None
        self._accum_sr: Optional[int] = None

        self._wpe_online: Optional[OnlineWPEProcessor] = None

    # контекст менеджер
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc, tb):
        self._buffer = None
        self._incoming_frames = 0
        self._accum = None
        self._accum_sr = None
        return False

    # Graph API
    def put_data(self, _source: str, data: FrameContainer) -> None:
        with self._lock:
            self._buffer = data.clone() if self._buffer is None else self._buffer.append(data)
            self._incoming_frames += data.length_frames

    def get_data(self) -> FrameContainer | None:
        with self._lock:
            if not self._buffer or self._incoming_frames == 0:
                return None

            tail = self._buffer.get_end_frames(self._incoming_frames)
            out = self._process_with_accumulator(tail)  # ключевая логика
            self._buffer = self._buffer.get_end_seconds(LONG_BUFFER_SIZE_SEC)
            self._incoming_frames = 0
            return out

    def _process_with_accumulator(self, data: FrameContainer) -> FrameContainer:
        # проверка формата: нода ждёт float32 (4 байта на сэмпл)
        if self._config.require_float32 and data.audio_format.sample_size != 4:
            raise ValueError(
                f"{self.name}: требуется float32 на входе; пришло sample_size={data.audio_format.sample_size} "
                "(вставьте Float32Mono на входе)"
            )

        sr = int(data.rate)
        x_new = np.frombuffer(data.frame_data, dtype="<f4").astype(np.float32)
        n_in = x_new.size

        # инициализация/сброс аккумулятора на смене SR
        if self._accum is None or (self._accum_sr is not None and self._accum_sr != sr):
            # предзаполняем нулями до минимального буфера
            need = int(max(0.0, self._config.wpe_min_buffer_sec) * sr)
            self._accum = np.zeros((need,), dtype=np.float32)
            self._accum_sr = sr
            logger.info(
                "%s: init accumulator with %.0f ms of zeros (sr=%d)",
                self.name, self._config.wpe_min_buffer_sec * 1000, sr
            )

        # накапливаем вход
        self._accum = np.concatenate([self._accum, x_new]) if self._accum.size else x_new

        # обработать ВЕСЬ аккумулятор целиком
        y_full = self._run_full_chain(self._accum, sr)

        # отдать РОВНО столько, сколько пришло, с конца
        if y_full.size < n_in:
            # на всякий случай, не должно случаться из-за стыковки STFT
            logger.warning("%s: processed shorter than input; pass-through", self.name)
            y_out = x_new
        else:
            y_out = y_full[-n_in:].astype(np.float32)

        # сократить аккумулятор до keep_context (после обработки!)
        keep = int(max(0.0, self._config.wpe_keep_context_sec) * sr)
        keep = max(keep, n_in)  # держим минимум последнего чанка
        self._accum = y_full[-keep:].astype(np.float32)

        # вернуть как FrameContainer (float32 bytes)
        return FrameContainer.from_config(
            data,
            cast(bytes, y_out.astype("<f4").tobytes()),
        )
    
    def _run_full_chain(self, x_full: np.ndarray, sr: int) -> np.ndarray:
        logger.info("GGG1")
        x = x_full.astype(np.float32, copy=False)

        # 1) WPE по всему накопленному буферу (если включен)
        if self._config.enable_wpe:
            if self._wpe_online is None or self._wpe_online.state.sr != sr:
                # Мягкий «strong» пресет
                self._wpe_online = OnlineWPEProcessor(
                    sr=sr, 
                    n_fft=2048, 
                    hop=512, 
                    taps=12, 
                    delay=3, 
                    alpha=0.92,
                )

        if self._config.enable_wpe and self._wpe_online is not None:
            before = peak_dbfs(x)
            x = self._wpe_online.process_chunk(x)
            after = peak_dbfs(x)
            logger.info("%s.wpe(online): peak %.2f → %.2f dBFS (len=%.0f ms)",
                        self.name, before, after, 1000.0 * len(x) / sr)

        # 2) Нормализация пика (headroom)
        if self._config.enable_normalize:
            before = peak_dbfs(x)
            x = normalize_peak_headroom(x, self._config.headroom_db)
            after = peak_dbfs(x)
            logger.info("%s.normalize: peak %.2f → %.2f dBFS (headroom=%.1f dB)",
                        self.name, before, after, self._config.headroom_db)

        # 3) Мягкий лимитер — страхуем «любые» выбросы
        if self._config.enable_limiter:
            before = peak_dbfs(x)
            x = soft_limit_tanh(x, self._config.true_peak_dbfs)
            after = peak_dbfs(x)
            logger.info("%s.limiter: peak %.2f → %.2f dBFS (ceil=%.1f dBFS)",
                        self.name, before, after, self._config.true_peak_dbfs)

        # 4) Фильтры HPF/LPF (zero-phase)
        if self._config.enable_filters:
            x = apply_filters_zero_phase(
                x, sr,
                f_low=self._config.hpf_hz,
                lpf_ratio_to_nyq=self._config.lpf_ratio_to_nyquist,
                order=self._config.filter_order,
            )
            logger.info("%s.filters: HPF=%s, LPF≈%.0f Hz, order=%d",
                        self.name,
                        f"{self._config.hpf_hz:.0f} Hz" if (self._config.hpf_hz and self._config.hpf_hz > 0) else "off",
                        min(0.5 * sr * self._config.lpf_ratio_to_nyquist, 0.5 * sr - 200.0),
                        self._config.filter_order)

        # защита от единичных NaN/Inf и финальный клип
        x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
        x = np.clip(x, -1.0, 1.0).astype(np.float32)
        return x


def peak_dbfs(x: np.ndarray) -> float:
    m = float(np.max(np.abs(x)) + 1e-12)
    return 20.0 * np.log10(m)

def normalize_peak_headroom(x: np.ndarray, headroom_db: float) -> np.ndarray:
    # целевой пик: -headroom_db от 0 dBFS
    target_lin = 10 ** (-headroom_db / 20.0)
    peak = np.max(np.abs(x)) + 1e-12
    gain = min(1.0, target_lin / peak)
    return (x * gain).astype(np.float32)

def soft_limit_tanh(x: np.ndarray, ceil_dbfs: float) -> np.ndarray:
    # очень мягкий “лимитер”: нормируем к целевому пику и сжимаем tanh
    ceil = 10 ** (ceil_dbfs / 20.0)  # например -1.8 dBFS
    peak = np.max(np.abs(x)) + 1e-12
    if peak > ceil:
        x = x / peak * ceil
    # дополнительные выбросы сгладит tanh при больших амплитудах
    return np.tanh(x / max(ceil, 1e-3)) * ceil


def apply_filters_zero_phase(
    x: np.ndarray,
    sr: int,
    f_low: Optional[float],
    lpf_ratio_to_nyq: float,
    order: int,
) -> np.ndarray:
    y = x.astype(np.float32, copy=False)
    if f_low and f_low > 0:
        nyq = 0.5 * sr
        wn = max(1e-6, min(0.999999, f_low / nyq))
        b, a = butter(order, wn, btype="highpass")
        y = filtfilt(b, a, y).astype(np.float32)
    # LPF на долю Найквиста (защита от ультразвука/дзвона)
    nyq = 0.5 * sr
    f_hi = max(10.0, min(nyq * lpf_ratio_to_nyq, nyq * 0.98))
    wn = max(1e-6, min(0.999999, f_hi / nyq))
    b, a = butter(order, wn, btype="lowpass")
    y = filtfilt(b, a, y).astype(np.float32)
    return y


class DenoiserWrapper:
    def __init__(self, sr: int, model: str = "dns48", device: str = "cpu"):
        self.device = torch.device(device)
        self.sr = sr
        # Загрузим предобученную модель (dns48/dns64/master64)
        self.model = (
            pretrained.dns48().to(self.device) if model=="dns48" else 
            (
                pretrained.dns64().to(self.device) 
                if model=="dns64" else 
                pretrained.master64().to(self.device)
            )
        )
        self.model.eval()

    def __call__(self, x_f32: np.ndarray) -> np.ndarray:
        # вход: float32 моно [-1,1], sr исходный
        wav = torch.from_numpy(x_f32).float().unsqueeze(0).to(self.device) # [1, T]
        wav = convert_audio(wav, self.sr, self.sr, self.model.audio_channels) # ensure mono
        with torch.inference_mode():
            y = self.model(wav)[0]
        return np.clip(y.squeeze(0).cpu().numpy().astype(np.float32), -1.0, 1.0)
