# plugins/limiter.py
from typing import Annotated
from pydantic import BaseModel, Field

import numpy as np

from .registry import plugin
from synchro.audio.frame_container import FrameContainer
from synchro.config.audio_format import AudioFormat, AudioFormatType


class LimiterCfg(BaseModel):
    threshold_dbfs: Annotated[float, Field(le=-0.1, ge=-60)] = -1.0
    emit_format: AudioFormatType = AudioFormatType.FLOAT_32


@plugin("limiter")
def limiter(fc: FrameContainer, cfg_dict) -> FrameContainer:
    cfg = LimiterCfg.model_validate(cfg_dict or {})
    thr = 10 ** (cfg.threshold_dbfs / 20.0)
    x = fc.as_float32()
    m = np.maximum(1.0, np.abs(x) / thr)
    y = (x / m).astype("<f4")
    out = fc.with_new_data(y.tobytes())
    out.audio_format = AudioFormat(format_type=cfg.emit_format)
    return out
