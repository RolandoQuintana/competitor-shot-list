"""OpenRouter vision backend (HTTP mocked)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from shotlist.config import Settings, get_settings
from shotlist.vision.openrouter import OpenRouterVisionBackend


def _settings(**overrides: object) -> Settings:
    base = replace(
        get_settings(),
        openrouter_api_key="test-key",
        openrouter_vision_model="test/vision-model",
        vision_request_delay_sec=0.0,
        vision_max_retries=2,
    )
    return replace(base, **overrides) if overrides else base


@pytest.fixture
def settings() -> Settings:
    return _settings()


def test_openrouter_vision_requires_api_key() -> None:
    with pytest.raises(ValueError, match="API key"):
        OpenRouterVisionBackend(_settings(openrouter_api_key=None))


@pytest.mark.asyncio
async def test_openrouter_vision_returns_model_content(
    settings: Settings, tmp_path: Path
) -> None:
    image = tmp_path / "frame.jpg"
    image.write_bytes(b"fake-jpeg")

    with patch(
        "shotlist.vision.openrouter.post_chat_completions",
        new=AsyncMock(return_value="Person at desk with laptop."),
    ) as mock_post:
        backend = OpenRouterVisionBackend(settings)
        text = await backend.describe_frame(str(image))

    assert text == "Person at desk with laptop."
    mock_post.assert_awaited_once()
    payload = mock_post.await_args.args[1]
    assert payload["model"] == "test/vision-model"
