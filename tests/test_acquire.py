"""YouTube acquisition (yt-dlp) unit tests — no network."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from shotlist.acquire import (
    acquire_youtube_short,
    metadata_from_info,
    parse_youtube_video_id,
    validate_youtube_url,
)
from shotlist.config import Settings
from shotlist.errors import InvalidVideoUrlError, VideoTooLongError


def _settings(tmp_path: Path, max_duration: float = 90.0) -> Settings:
    return Settings(
        output_dir=tmp_path / "out",
        vision_backend="mock",
        transcript_backend="stub",
        frame_interval_sec=1.0,
        max_video_duration_sec=max_duration,
        frame_long_edge_px=768,
        frame_jpeg_quality=85,
        whisper_model="small",
        whisper_compute_type="int8",
        pipeline_version="0.1.0",
        scratch_dir=tmp_path / "scratch",
    )


def test_parse_youtube_video_id_shorts_url() -> None:
    assert parse_youtube_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_parse_youtube_video_id_watch_url() -> None:
    assert (
        parse_youtube_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ&feature=share")
        == "dQw4w9WgXcQ"
    )


def test_parse_youtube_video_id_youtu_be() -> None:
    assert parse_youtube_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_validate_youtube_url_rejects_non_youtube() -> None:
    with pytest.raises(InvalidVideoUrlError, match="YouTube"):
        validate_youtube_url("https://example.com/video")


def test_metadata_from_info_maps_fields() -> None:
    info = {
        "id": "abc123xyz01",
        "webpage_url": "https://www.youtube.com/shorts/abc123xyz01",
        "title": "Sample Short",
        "channel": "Test Channel",
        "duration": 42.5,
        "thumbnail": "https://i.ytimg.com/vi/abc123xyz01/hqdefault.jpg",
    }
    meta = metadata_from_info(info)
    assert meta.video_id == "abc123xyz01"
    assert meta.title == "Sample Short"
    assert meta.channel == "Test Channel"
    assert meta.duration_sec == 42.5
    assert meta.thumbnail_url == info["thumbnail"]


def test_acquire_rejects_over_max_duration(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path, max_duration=90.0)
    info = {
        "id": "abc123xyz01",
        "webpage_url": "https://www.youtube.com/shorts/abc123xyz01",
        "title": "Long",
        "channel": "Ch",
        "duration": 120.0,
    }

    def fake_run(cmd: list[str], **kwargs):  # noqa: ANN003
        if "--dump-single-json" in cmd:
            return MagicMock(returncode=0, stdout=json.dumps(info), stderr="")
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr("shotlist.acquire.subprocess.run", fake_run)

    with pytest.raises(VideoTooLongError, match="120"):
        acquire_youtube_short("https://www.youtube.com/shorts/abc123xyz01", settings)


def test_acquire_downloads_to_scratch(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    info = {
        "id": "abc123xyz01",
        "webpage_url": "https://www.youtube.com/shorts/abc123xyz01",
        "title": "Short",
        "channel": "Ch",
        "duration": 30.0,
    }
    def fake_run(cmd: list[str], **kwargs):  # noqa: ANN003
        if "--dump-single-json" in cmd:
            return MagicMock(returncode=0, stdout=json.dumps(info), stderr="")
        if any(part.endswith("yt-dlp") or part == "yt-dlp" for part in cmd) and "-o" in cmd:
            out_template = cmd[cmd.index("-o") + 1]
            out_path = Path(out_template.replace("%(ext)s", "mp4"))
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(b"fake")
            return MagicMock(returncode=0, stdout="", stderr="")
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr("shotlist.acquire.subprocess.run", fake_run)

    acquired = acquire_youtube_short("https://www.youtube.com/shorts/abc123xyz01", settings)
    assert acquired.video_path.name == "video.mp4"
    assert acquired.video_path.is_file()
    assert acquired.scratch_dir.parent == settings.scratch_dir
    assert acquired.scratch_dir.name.startswith("abc123xyz01-")
    assert acquired.metadata.video_id == "abc123xyz01"


def test_acquire_invalid_url_from_yt_dlp(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path)

    def fake_run(cmd: list[str], **kwargs):  # noqa: ANN003
        return MagicMock(returncode=1, stdout="", stderr="ERROR: Video unavailable")

    monkeypatch.setattr("shotlist.acquire.subprocess.run", fake_run)

    with pytest.raises(InvalidVideoUrlError, match="unavailable"):
        acquire_youtube_short("https://www.youtube.com/shorts/notreal0000", settings)
