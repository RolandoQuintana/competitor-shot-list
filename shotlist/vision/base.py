"""Vision backend protocol."""

from __future__ import annotations

from abc import ABC, abstractmethod


class VisionBackend(ABC):
    @abstractmethod
    async def describe_frame(self, image_path: str) -> str:
        """Return a concise visual description for one frame."""
