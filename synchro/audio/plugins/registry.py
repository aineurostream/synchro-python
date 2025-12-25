# plugins/registry.py
from typing import Callable, Dict, Any, Protocol

from synchro.audio.frame_container import FrameContainer

class PluginFn(Protocol):
    def __call__(self, fc: FrameContainer, cfg: Any) -> FrameContainer: ...

REGISTRY: Dict[str, PluginFn] = {}

def plugin(name: str):
    def wrapper(fn: PluginFn) -> PluginFn:
        if name in REGISTRY:
            raise ValueError(f"Plugin with name '{name}' is already registered")
        
        REGISTRY[name] = fn
        return fn
    
    return wrapper
