# plugins/runner.py
import logging
from typing import Any, List
from pydantic import BaseModel

from .registry import REGISTRY
from synchro.audio.frame_container import FrameContainer

logger = logging.getLogger(__name__)

class PluginSpec(BaseModel):
    name: str
    config: Any = {}  # сюда попадёт словарь, который плагин сам валидирует своей моделью


def run_plugins(fc: FrameContainer, chain: List[PluginSpec]) -> FrameContainer:
    out = fc
    for step, spec in enumerate(chain, 1):
        fn = REGISTRY.get(spec.name)
        if fn is None:
            logger.warning("Plugin '%s' not found — skipping", spec.name)
            continue

        try:
            out = fn(out, spec.config)
        except Exception as e:
            logger.exception("Plugin '%s' failed at step %d: %s", spec.name, step, e)
            # по вкусу: либо падаем, либо пропускаем
            raise

    return out
