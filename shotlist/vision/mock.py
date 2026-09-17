"""Placeholder vision for CI and zero-API runs."""

from __future__ import annotations

from pathlib import Path

from shotlist.vision.base import VisionBackend


class MockVisionBackend(VisionBackend):
    async def describe_frame(self, image_path: str) -> str:
        name = Path(image_path).name
        return f"[mock] Placeholder vision for {name}. No on-screen text detected."
