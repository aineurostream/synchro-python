# plugins/high_pass.py
from typing import Annotated
from pydantic import BaseModel, Field

import numpy as np
from scipy.signal import butter, lfilter

from .registry import plugin
from synchro.audio.frame_container import FrameContainer
from synchro.config.audio_format import AudioFormat, AudioFormatType


class HighPassCfg(BaseModel):
    cutoff_hz: Annotated[float, Field(gt=10, lt=1000)] = 100.0
    order: Annotated[int, Field(ge=1, le=8)] = 4
    emit_format: AudioFormatType = AudioFormatType.FLOAT_32


@plugin("high_pass")
def high_pass(fc: FrameContainer, cfg_dict) -> FrameContainer:
    cfg = HighPassCfg.model_validate(cfg_dict or {})
    sr = int(fc.rate)
    x = fc.as_float32()
    # поддержка многоканала: reshape(N, C) если известно число каналов
    C = fc.channels_or_1()
    X = x.reshape(-1, C)
    b, a = butter(cfg.order, cfg.cutoff_hz / (0.5 * sr), btype="high", analog=False)
    Y = np.vstack([lfilter(b, a, X[:, c]) for c in range(C)]).T.astype("<f4")
    out = fc.with_new_data(Y.reshape(-1).tobytes())
    out.audio_format = AudioFormat(format_type=cfg.emit_format)
    return out