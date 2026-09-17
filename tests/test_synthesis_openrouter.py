"""OpenRouter LLM synthesis (HTTP mocked)."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from shotlist.config import Settings
from shotlist.errors import SynthesisError
from shotlist.models import VideoMetadata
from shotlist.synthesis import extract_json_object, synthesize_shot_list_openrouter
from shotlist.transcribe import TranscriptResult


def _settings() -> Settings:
    return Settings(
        output_dir=Path("./output"),
        scratch_dir=Path("/tmp/shotlist"),
        vision_backend="openrouter",
        transcript_backend="whisper",
        frame_interval_sec=1.0,
        max_video_duration_sec=90.0,
        frame_long_edge_px=768,
        frame_jpeg_quality=85,
        whisper_model="small",
        whisper_compute_type="int8",
        pipeline_version="0.1.0",
        openrouter_api_key="test-key",
        openrouter_base_url="https://openrouter.ai/api/v1",
        openrouter_vision_model="test/vision",
        openrouter_synthesis_model="test/synthesis",
        openrouter_http_referer=None,
        openrouter_app_title="competitor-shot-list",
        vision_prompt="Describe the frame.",
        vision_request_delay_sec=0.0,
        vision_max_retries=2,
        vision_concurrency=1,
        synthesis_max_retries=3,
        job_timeout_sec=1800.0,
    )


def _video() -> VideoMetadata:
    return VideoMetadata(
        url="https://www.youtube.com/shorts/abc",
        video_id="abc",
        title="Sample",
        channel="Ch",
        duration_sec=10.0,
        analyzed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def test_extract_json_object_strips_markdown_fence() -> None:
    payload = extract_json_object('```json\n{"shots": []}\n```')
    assert payload == {"shots": []}


@pytest.mark.asyncio
async def test_synthesis_retries_after_invalid_json() -> None:
    settings = replace(_settings(), synthesis_max_retries=2)
    valid = {
        "shots": [
            {
                "index": 1,
                "start_sec": 0.0,
                "end_sec": 10.0,
                "time_label": "0–10s",
                "shot_type": "talking_head",
                "visual": "Creator on camera",
                "dialogue": "Hello",
                "on_screen_text": "",
                "framing": "medium",
                "role": "hook",
            }
        ]
    }
    responses = ["not json at all", json.dumps(valid)]

    with patch(
        "shotlist.synthesis.chat_completion",
        new=AsyncMock(side_effect=responses),
    ):
        shot_list = await synthesize_shot_list_openrouter(
            settings=settings,
            video=_video(),
            duration_sec=10.0,
            frame_interval_sec=1.0,
            vision_descriptions=["frame note"],
            transcript=TranscriptResult(
                full_text="Hello",
                segments=[{"start_sec": 0.0, "end_sec": 10.0, "text": "Hello"}],
            ),
            pipeline_version="0.1.0",
        )

    assert len(shot_list.shots) == 1
    assert shot_list.analysis.models["synthesis"] == "test/synthesis"


@pytest.mark.asyncio
async def test_synthesis_raises_after_exhausted_retries() -> None:
    settings = replace(_settings(), synthesis_max_retries=2)
    with patch(
        "shotlist.synthesis.chat_completion",
        new=AsyncMock(return_value="still not json"),
    ):
        with pytest.raises(SynthesisError, match="failed after"):
            await synthesize_shot_list_openrouter(
                settings=settings,
                video=_video(),
                duration_sec=10.0,
                frame_interval_sec=1.0,
                vision_descriptions=["note"],
                transcript=TranscriptResult(full_text="", segments=[]),
                pipeline_version="0.1.0",
            )
