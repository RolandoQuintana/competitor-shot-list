"""Vision backends for per-frame description."""

from __future__ import annotations

from shotlist.config import Settings
from shotlist.vision.base import VisionBackend
from shotlist.vision.mock import MockVisionBackend


def create_vision_backend(settings: Settings) -> VisionBackend:
    name = settings.vision_backend
    if name == "mock":
        return MockVisionBackend()
    raise ValueError(
        f"Unsupported VISION_BACKEND={name!r} in this build; use mock for CI"
    )


__all__ = ["VisionBackend", "MockVisionBackend", "create_vision_backend"]
