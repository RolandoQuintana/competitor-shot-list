"""OpenRouter per-frame vision."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from shotlist.config import Settings
from shotlist.openrouter import post_chat_completions
from shotlist.vision.base import VisionBackend


class OpenRouterVisionBackend(VisionBackend):
    def __init__(self, settings: Settings) -> None:
        if not settings.openrouter_api_key:
            raise ValueError(
                "OpenRouter API key is required for openrouter vision backend"
            )
        self._settings = settings
        self._model = settings.openrouter_vision_model
        self._prompt = settings.vision_prompt

    async def describe_frame(self, image_path: str) -> str:
        raw = Path(image_path).read_bytes()
        b64 = base64.b64encode(raw).decode("ascii")
        data_url = f"data:image/jpeg;base64,{b64}"
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": self._prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
        }
        try:
            text = await post_chat_completions(
                self._settings,
                payload,
                max_retries=self._settings.vision_max_retries,
                delay_after_sec=self._settings.vision_request_delay_sec,
            )
            return text or "[vision unavailable]"
        except RuntimeError as exc:
            return f"[vision error] {exc}"
