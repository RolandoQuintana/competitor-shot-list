"""Analyze pipeline orchestration (fixture / local media path)."""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from dataclasses import replace

from shotlist.config import Settings, get_settings
from shotlist.errors import EmptyShotsError
from shotlist.media import extract_audio, extract_frames, probe_duration
from shotlist.models import VideoMetadata
from shotlist.persist import persist_shot_list
from shotlist.synthesis import synthesize_shot_list
from shotlist.transcribe import transcribe_audio
from shotlist.vision import create_vision_backend

FIXTURE_VIDEO_ID = "ci-sample"
FIXTURE_RELATIVE = Path("fixtures") / "ci-sample.mp4"


def bundled_fixture_video_path() -> Path:
    return Path(__file__).resolve().parent / FIXTURE_RELATIVE


def fixture_video_metadata(duration_sec: float) -> VideoMetadata:
    return VideoMetadata(
        url="fixture://ci-sample",
        video_id=FIXTURE_VIDEO_ID,
        title="CI Sample Short",
        channel="Fixture",
        duration_sec=duration_sec,
        analyzed_at=datetime.now(timezone.utc),
    )


async def _describe_frames(frame_paths: list[Path], settings: Settings) -> list[str]:
    backend = create_vision_backend(settings)
    descriptions: list[str] = []
    errors = 0
    for path in frame_paths:
        try:
            text = await backend.describe_frame(str(path))
            if text.startswith("[vision error]"):
                errors += 1
            descriptions.append(text)
        except Exception as exc:  # noqa: BLE001
            errors += 1
            descriptions.append(f"[vision error] {exc}")
    return descriptions


async def analyze_local_video(
    video_path: Path,
    video: VideoMetadata,
    settings: Settings | None = None,
) -> Path:
    """
    Run media → transcript → mock vision → synthesis → persist.

    Returns the output directory for the video id.
    """
    settings = settings or get_settings()
    work = Path(tempfile.mkdtemp(prefix="shotlist-", dir="/tmp"))

    try:
        duration = probe_duration(video_path)
        if duration > settings.max_video_duration_sec:
            raise ValueError(
                f"Video duration {duration:.1f}s exceeds max "
                f"{settings.max_video_duration_sec}s"
            )

        wav_path = work / "audio.wav"
        frames_dir = work / "frames"
        extract_audio(video_path, wav_path)
        frames = extract_frames(
            video_path,
            frames_dir,
            interval_sec=settings.frame_interval_sec,
            long_edge=settings.frame_long_edge_px,
            jpeg_quality=settings.frame_jpeg_quality,
            max_duration=settings.max_video_duration_sec,
        )
        if not frames:
            raise RuntimeError("FFmpeg produced no frames")

        transcript = transcribe_audio(
            wav_path, settings, duration_sec=min(duration, settings.max_video_duration_sec)
        )
        vision_lines = await _describe_frames(frames, settings)

        shot_list = synthesize_shot_list(
            video=video,
            duration_sec=min(duration, settings.max_video_duration_sec),
            frame_interval_sec=settings.frame_interval_sec,
            vision_descriptions=vision_lines,
            transcript=transcript,
            pipeline_version=settings.pipeline_version,
        )

        if not shot_list.shots:
            raise EmptyShotsError("synthesis produced empty shots[]")

        return persist_shot_list(shot_list, settings.output_dir)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def ci_fixture_settings(settings: Settings | None = None) -> Settings:
    """Force mock vision + stub transcript for bundled fixture runs."""
    base = settings or get_settings()
    return replace(
        base,
        vision_backend="mock",
        transcript_backend="stub",
    )


def analyze_fixture(settings: Settings | None = None) -> Path:
    """Analyze the bundled CI sample video (no YouTube, no paid APIs)."""
    path = bundled_fixture_video_path()
    if not path.is_file():
        raise FileNotFoundError(f"Bundled fixture video missing: {path}")
    duration = probe_duration(path)
    video = fixture_video_metadata(duration)
    return asyncio.run(
        analyze_local_video(path, video, settings=ci_fixture_settings(settings))
    )
