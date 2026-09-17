"""Pipeline guards for real OpenRouter analyze."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest

from shotlist.config import Settings
from shotlist.errors import JobTimeoutError
from shotlist.pipeline import analyze_local_video, fixture_video_metadata


def _base_settings() -> Settings:
    from shotlist.config import get_settings

    return get_settings()


@pytest.mark.asyncio
async def test_analyze_requires_openrouter_key_when_not_mock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    settings = replace(
        _base_settings(),
        vision_backend="openrouter",
        openrouter_api_key=None,
        output_dir=tmp_path,
    )
    video_path = tmp_path / "v.mp4"
    video_path.write_bytes(b"x")

    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        await analyze_local_video(
            video_path,
            fixture_video_metadata(1.0),
            settings=settings,
        )


@pytest.mark.asyncio
async def test_job_timeout_raises(tmp_path: Path) -> None:
    settings = replace(
        _base_settings(),
        vision_backend="mock",
        transcript_backend="stub",
        job_timeout_sec=0.01,
        output_dir=tmp_path,
    )
    fixture = Path(__file__).resolve().parents[1] / "shotlist/fixtures/ci-sample.mp4"
    if not fixture.is_file():
        pytest.skip("bundled fixture missing")

    async def slow_impl(*_args: object, **_kwargs: object) -> Path:
        await __import__("asyncio").sleep(1)
        return tmp_path

    with pytest.raises(JobTimeoutError, match="JOB_TIMEOUT_SEC"):
        with patch("shotlist.pipeline._analyze_local_video_impl", new=slow_impl):
            await analyze_local_video(
                fixture,
                fixture_video_metadata(3.0),
                settings=settings,
            )
