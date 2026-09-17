"""Vision backends for per-frame description."""

from __future__ import annotations

from shotlist.config import Settings
from shotlist.vision.base import VisionBackend
from shotlist.vision.mock import MockVisionBackend
from shotlist.vision.openrouter import OpenRouterVisionBackend


def create_vision_backend(settings: Settings) -> VisionBackend:
    name = settings.vision_backend
    if name == "mock":
        return MockVisionBackend()
    if name == "openrouter":
        return OpenRouterVisionBackend(settings)
    raise ValueError(f"Unsupported VISION_BACKEND={name!r}; use mock or openrouter")


__all__ = [
    "VisionBackend",
    "MockVisionBackend",
    "OpenRouterVisionBackend",
    "create_vision_backend",
]
