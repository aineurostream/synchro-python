import numpy as np
from dataclasses import dataclass
from typing import Optional, Tuple
from scipy.signal import get_window

def _stable_positive_inverse(x: np.ndarray, eps: float = 1e-8) -> np.ndarray:
    # 1/(x+eps), гарантирует положительность знаменателя
    return 1.0 / (np.real(x) + eps)

@dataclass
class OnlineWPEState:
    # Размерность по частоте и времени
    n_fft: int
    hop: int
    sr: int
    taps: int
    delay: int
    alpha: float  # сглаживание для PSD (0..1)

    # Состояния (заполняются при первом вызове)
    inv_cov: Optional[np.ndarray] = None         # (F, taps, taps) — R^{-1}
    filter_taps: Optional[np.ndarray] = None     # (F, taps)       — w
    power_est: Optional[np.ndarray] = None       # (F,)            — сглажённая PSD
    input_buf: Optional[np.ndarray] = None       # (taps+delay+1, F) — последние спектральные кадры

    # окно для STFT/OLA
    _window: Optional[np.ndarray] = None         # (n_fft,)
    _win_norm: float = 0.0

    def ensure_init(self):
        F = self.n_fft // 2 + 1
        if self.inv_cov is None:
            # начальные R^{-1}: единичные матрицы
            self.inv_cov = np.stack([np.eye(self.taps, dtype=np.complex64) for _ in range(F)], axis=0)
        if self.filter_taps is None:
            self.filter_taps = np.zeros((F, self.taps), dtype=np.complex64)
        if self.power_est is None:
            self.power_est = np.ones((F,), dtype=np.float32) * 1e-4
        if self.input_buf is None:
            self.input_buf = np.zeros((self.taps + self.delay + 1, F), dtype=np.complex64)
        if self._window is None:
            self._window = get_window("hann", self.n_fft, fftbins=True).astype(np.float32)
            # нормировка для OLA (Princen-Bradley для hann с hop=n_fft/4 даёт ≈1.0)
            # для общности посчитаем опытно на одном блоке:
            w = self._window
            self._win_norm = float((w**2).sum() / self.hop)

def stft_frames(x: np.ndarray, n_fft: int, hop: int, window: np.ndarray) -> np.ndarray:
    """
    rFFT кадры (T, F). Добавляем паддинг слева/справа кратный hop,
    чтобы сетка кадров укладывалась в сигнал без «ломаных» краёв.
    """
    L = x.size
    pad_left = n_fft - hop       # чтобы первый центр окна был внутри сигнала
    pad_right = (-(L + pad_left - n_fft) % hop)  # кратность hop
    x_pad = np.pad(x, (pad_left, pad_right), mode="constant")
    T = 1 + (x_pad.size - n_fft) // hop

    frames = np.lib.stride_tricks.as_strided(
        x_pad,
        shape=(T, n_fft),
        strides=(hop * x_pad.strides[0], x_pad.strides[0]),
        writeable=False,
    ).copy()
    frames *= window[None, :]
    X = np.fft.rfft(frames, n=n_fft, axis=1).astype(np.complex64)
    return X  # (T, F)

def istft_ola_norm(X: np.ndarray, n_fft: int, hop: int, window: np.ndarray) -> np.ndarray:
    """
    Корректная COLA-OLA: суммируем окна и нормируем по сумме window^2.
    """
    T, F = X.shape
    L = n_fft + hop * (T - 1)
    y = np.zeros((L,), dtype=np.float32)
    w = window.astype(np.float32)
    w2 = (w * w).astype(np.float32)
    weights = np.zeros_like(y)

    for t in range(T):
        frm = np.fft.irfft(X[t], n=n_fft).astype(np.float32)
        i0 = t * hop
        y[i0:i0 + n_fft] += frm * w
        weights[i0:i0 + n_fft] += w2

    # пер-семпловая нормировка
    weights = np.maximum(weights, 1e-8)
    y /= weights
    return y

def online_wpe_step(
    input_buffer: np.ndarray,       # (taps+delay+1, F)
    power_estimate: np.ndarray,     # (F,)
    inv_cov: np.ndarray,            # (F, taps, taps)
    filter_taps: np.ndarray,        # (F, taps)
    alpha: float,
    taps: int,
    delay: int,
    *,
    den_floor: float = 1e-6,        # ⬅ минимальный пол знаменателя
    psd_floor: float = 1e-7,        # ⬅ минимальный пол PSD
    gain_clip: float = 5.0,         # ⬅ клип усиления (по L2) на бин
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:

    F = input_buffer.shape[-1]
    window = input_buffer[:-delay - 1][::-1]   # (taps, F)
    window = window.T                          # (F, taps)

    # предсказание поздних отражений
    pred = input_buffer[-1] - np.sum(np.conjugate(filter_taps) * window, axis=1)  # (F,)

    # PSD-пол
    pe = np.maximum(power_estimate.astype(np.float32), psd_floor).astype(np.complex64)

    nominator   = np.einsum('fij,fj->fi', inv_cov, window)                # (F, taps)
    denominator = (alpha * pe) + np.einsum('fi,fi->f', np.conjugate(window), nominator)
    denominator = np.real(denominator).astype(np.float32)
    denominator = np.maximum(denominator, den_floor)

    kalman_gain = (nominator / denominator[:, None]).astype(np.complex64)

    # клип усиления на каждый F (чтобы не «взрывалось»)
    if gain_clip is not None and gain_clip > 0:
        norms = np.linalg.norm(kalman_gain, axis=1) + 1e-12  # (F,)
        scale = np.minimum(1.0, gain_clip / norms).astype(np.float32)
        kalman_gain = kalman_gain * scale[:, None]

    inv_cov_k = inv_cov - np.einsum('fj,fjm,fi->fim',
                                    np.conjugate(window), inv_cov, kalman_gain, optimize='optimal')
    inv_cov_k = inv_cov_k / alpha

    filter_taps_k = filter_taps + kalman_gain * np.conjugate(pred)[:, None]
    return pred, inv_cov_k, filter_taps_k

class OnlineWPEProcessor:
    def __init__(self, sr: int, n_fft: int = 1024, hop: int = 512,
                 taps: int = 12, delay: int = 3, alpha: float = 0.92,
                 wet: float = 0.85):  # ← добавили dry/wet
        self.state = OnlineWPEState(n_fft=n_fft, hop=hop, sr=sr, taps=taps, delay=delay, alpha=alpha)
        self.state.ensure_init()
        self.wet = float(np.clip(wet, 0.0, 1.0))
        self.window = get_window("hann", n_fft, fftbins=True).astype(np.float32)

    def process_chunk(self, x_f32: np.ndarray) -> np.ndarray:
        st = self.state
        st.ensure_init()
        X = stft_frames(x_f32.astype(np.float32), st.n_fft, st.hop, self.window)  # (T,F)
        T, F = X.shape
        buf = st.input_buf
        out_spec = np.empty_like(X)

        for t in range(T):
            buf[:-1] = buf[1:]
            buf[-1]  = X[t]

            # сглажённая мощность с полом
            pe = np.maximum(st.power_est, 1e-7).astype(np.float32)
            pe = st.alpha * pe + (1.0 - st.alpha) * (np.abs(X[t])**2).astype(np.float32)
            st.power_est = pe

            pred, st.inv_cov, st.filter_taps = online_wpe_step(
                buf, pe, st.inv_cov, st.filter_taps, st.alpha, st.taps, st.delay,
                den_floor=1e-6, psd_floor=1e-7, gain_clip=5.0
            )
            out_spec[t] = pred

        y_wet  = istft_ola_norm(out_spec, st.n_fft, st.hop, self.window)
        y_wet  = y_wet[st.n_fft - st.hop : st.n_fft - st.hop + x_f32.size].astype(np.float32)

        # dry/wet — чтобы убрать возможные остаточные артефакты
        y = (self.wet * y_wet + (1.0 - self.wet) * x_f32.astype(np.float32))
        return np.clip(y, -1.0, 1.0).astype(np.float32)
