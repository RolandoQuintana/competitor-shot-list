"""YouTube URL analyze wiring (mocked acquire + fixture media)."""

import json
import shutil
from datetime import datetime, timezone

import pytest

from shotlist.acquire import AcquiredVideo
from shotlist.models import ShotList, VideoMetadata
from shotlist.pipeline import analyze_youtube_url, bundled_fixture_video_path
from shotlist.validation import validate_shot_list_structure


@pytest.mark.integration
def test_analyze_youtube_url_uses_acquire_then_local_pipeline(
    tmp_path, monkeypatch
) -> None:
    fixture = bundled_fixture_video_path()
    if not fixture.is_file():
        pytest.skip(f"missing bundled fixture video: {fixture}")

    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("VISION_BACKEND", "mock")
    monkeypatch.setenv("TRANSCRIPT_BACKEND", "stub")
    monkeypatch.setenv("SCRATCH_DIR", str(tmp_path / "scratch"))

    scratch = tmp_path / "scratch" / "ytvid12345"
    scratch.mkdir(parents=True)
    video_copy = scratch / "video.mp4"
    video_copy.write_bytes(fixture.read_bytes())

    meta = VideoMetadata(
        url="https://www.youtube.com/shorts/ytvid12345",
        video_id="ytvid12345",
        title="Mock Short",
        channel="Test",
        duration_sec=5.0,
        analyzed_at=datetime.now(timezone.utc),
    )
    acquired = AcquiredVideo(video_path=video_copy, metadata=meta, scratch_dir=scratch)

    def fake_acquire(url: str, settings):  # noqa: ANN001
        assert "youtube.com" in url
        return acquired

    monkeypatch.setattr("shotlist.pipeline.acquire_youtube_short", fake_acquire)

    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not available")

    out_dir = analyze_youtube_url("https://www.youtube.com/shorts/ytvid12345")
    assert out_dir == tmp_path / "ytvid12345"
    payload = json.loads((out_dir / "shot-list.json").read_text(encoding="utf-8"))
    validate_shot_list_structure(ShotList.model_validate(payload))
