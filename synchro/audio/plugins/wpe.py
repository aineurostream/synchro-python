# plugins/wpe.py
import logging
from typing import Annotated
from pydantic import BaseModel, Field

import numpy as np
from scipy.signal import stft, istft

from .registry import plugin
from synchro.audio.frame_container import FrameContainer
from synchro.config.audio_format import AudioFormat, AudioFormatType

logger = logging.getLogger(__name__)


class WPECfg(BaseModel):
    taps: Annotated[int, Field(ge=1, le=30)] = 10
    delay: Annotated[int, Field(ge=0, le=10)] = 3
    iterations: Annotated[int, Field(ge=1, le=10)] = 3
    n_fft: Annotated[int, Field(ge=256, le=8192)] = 1024
    hop: int | None = None
    emit_format: AudioFormatType = AudioFormatType.FLOAT_32


@plugin("wpe")
def wpe(fc: FrameContainer, cfg_dict) -> FrameContainer:
    cfg = WPECfg.model_validate(cfg_dict or {})
    try:
        from nara_wpe import wpe as nara_wpe
    except Exception:
        logger.warning("nara-wpe not installed — skipping WPE")
        return fc

    C = fc.channels_or_1()
    if C < 2:
        logger.info("WPE: mono input — skipping")
        return fc

    sr = int(fc.rate)
    hop = cfg.hop or cfg.n_fft // 4
    x = fc.as_float32().reshape(-1, C)

    # STFT по каналам
    Z = []
    for c in range(C):
        _, _, Zc = stft(x[:, c], fs=sr, nperseg=cfg.n_fft, noverlap=cfg.n_fft - hop,
                        nfft=cfg.n_fft, return_onesided=True, boundary=None, padded=False)
        Z.append(Zc)
    T_min = min(z.shape[1] for z in Z)
    Z = [z[:, :T_min] for z in Z]
    Y = np.stack(Z, axis=-1).astype(np.complex64)  # (F,T,C)

    Yd = nara_wpe.wpe(Y, taps=cfg.taps, delay=cfg.delay, iterations=cfg.iterations)

    y = []
    for c in range(C):
        _, yc = istft(Yd[:, :, c], fs=sr, nperseg=cfg.n_fft, noverlap=cfg.n_fft - hop,
                      nfft=cfg.n_fft, input_onesided=True, boundary=None)
        y.append(yc.astype(np.float32))
    Tm = min(len(t) for t in y)
    Ytd = np.stack([t[:Tm] for t in y], axis=1).reshape(-1).astype("<f4")

    out = fc.with_new_data(Ytd.tobytes())
    out.audio_format = AudioFormat(format_type=cfg.emit_format)
    return out