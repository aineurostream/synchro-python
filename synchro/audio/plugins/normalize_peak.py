# plugins/normalize_peak.py
from typing import Annotated
from pydantic import BaseModel, Field

import numpy as np

from .registry import plugin
from synchro.audio.frame_container import FrameContainer
from synchro.config.audio_format import AudioFormat, AudioFormatType


class NormalizePeakCfg(BaseModel):
    target_dbfs: Annotated[float, Field(le=-0.1, ge=-60)] = -1.0  # например -1 dBFS
    emit_format: AudioFormatType = AudioFormatType.FLOAT_32  # выходной формат контейнера


@plugin("normalize_peak")
def normalize_peak(fc: FrameContainer, cfg_dict) -> FrameContainer:
    cfg = NormalizePeakCfg.model_validate(cfg_dict or {})
    x = fc.as_float32()  # [-1..1], 1D или interleaved
    peak = float(np.max(np.abs(x)) + 1e-12)
    gain = 10 ** (cfg.target_dbfs / 20.0) / peak
    y = np.clip(x * gain, -1.0, 1.0).astype("<f4")
    out = fc.with_new_data(y.tobytes())
    out.audio_format = AudioFormat(format_type=cfg.emit_format)
    return out
