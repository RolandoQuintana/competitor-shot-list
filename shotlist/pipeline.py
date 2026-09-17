"""Analyze pipeline orchestration (fixture / local media path)."""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from dataclasses import replace

from shotlist.acquire import AcquiredVideo, acquire_youtube_short
from shotlist.config import Settings, get_settings
from shotlist.errors import (
    EmptyShotsError,
    JobTimeoutError,
    MissingOpenRouterApiKeyError,
    VideoTooLongError,
)
from shotlist.media import extract_audio, extract_frames, probe_duration
from shotlist.models import VideoMetadata
from shotlist.persist import persist_shot_list
from shotlist.synthesis import synthesize_shot_list, synthesize_shot_list_openrouter
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


def _require_openrouter_key(settings: Settings) -> None:
    if settings.vision_backend == "openrouter" and not settings.openrouter_api_key:
        raise MissingOpenRouterApiKeyError(
            "OPENROUTER_API_KEY is required when VISION_BACKEND=openrouter"
        )


async def _describe_frames(
    frame_paths: list[Path], settings: Settings
) -> tuple[list[str], int]:
    backend = create_vision_backend(settings)
    sem = asyncio.Semaphore(max(1, settings.vision_concurrency))
    descriptions: list[str] = [""] * len(frame_paths)
    errors = 0

    async def one(idx: int, path: Path) -> None:
        nonlocal errors
        async with sem:
            try:
                text = await backend.describe_frame(str(path))
                if text.startswith("[vision error]"):
                    errors += 1
                descriptions[idx] = text
            except Exception as exc:  # noqa: BLE001
                errors += 1
                descriptions[idx] = f"[vision error] {exc}"

    await asyncio.gather(*(one(i, p) for i, p in enumerate(frame_paths)))
    return descriptions, errors


async def _analyze_local_video_impl(
    video_path: Path,
    video: VideoMetadata,
    settings: Settings,
) -> Path:
    scratch_root = settings.scratch_dir
    scratch_root.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="job-", dir=str(scratch_root)))

    try:
        duration = probe_duration(video_path)
        if duration > settings.max_video_duration_sec:
            raise VideoTooLongError(
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

        capped_duration = min(duration, settings.max_video_duration_sec)
        transcript = transcribe_audio(
            wav_path, settings, duration_sec=capped_duration
        )
        vision_lines, vision_errors = await _describe_frames(frames, settings)

        if settings.vision_backend == "mock":
            shot_list = synthesize_shot_list(
                video=video,
                duration_sec=capped_duration,
                frame_interval_sec=settings.frame_interval_sec,
                vision_descriptions=vision_lines,
                transcript=transcript,
                pipeline_version=settings.pipeline_version,
                vision_error_count=vision_errors,
            )
        else:
            shot_list = await synthesize_shot_list_openrouter(
                settings=settings,
                video=video,
                duration_sec=capped_duration,
                frame_interval_sec=settings.frame_interval_sec,
                vision_descriptions=vision_lines,
                transcript=transcript,
                pipeline_version=settings.pipeline_version,
                vision_error_count=vision_errors,
            )

        if not shot_list.shots:
            raise EmptyShotsError("synthesis produced empty shots[]")

        return persist_shot_list(shot_list, settings.output_dir)
    finally:
        shutil.rmtree(work, ignore_errors=True)


async def analyze_local_video(
    video_path: Path,
    video: VideoMetadata,
    settings: Settings | None = None,
) -> Path:
    """
    Run media → transcript → vision → synthesis → persist.

    Returns the output directory for the video id.
    """
    settings = settings or get_settings()
    _require_openrouter_key(settings)
    try:
        return await asyncio.wait_for(
            _analyze_local_video_impl(video_path, video, settings),
            timeout=settings.job_timeout_sec,
        )
    except TimeoutError:
        raise JobTimeoutError(
            f"analyze job exceeded JOB_TIMEOUT_SEC={settings.job_timeout_sec:g}"
        ) from None


def ci_fixture_settings(settings: Settings | None = None) -> Settings:
    """Force mock vision + stub transcript for bundled fixture runs."""
    base = settings or get_settings()
    return replace(
        base,
        vision_backend="mock",
        transcript_backend="stub",
    )


def analyze_youtube_url(url: str, settings: Settings | None = None) -> Path:
    """Acquire a public Short via yt-dlp, then run local media prep and persist."""
    settings = settings or get_settings()
    acquired: AcquiredVideo | None = None
    try:
        acquired = acquire_youtube_short(url, settings)
        return asyncio.run(
            analyze_local_video(acquired.video_path, acquired.metadata, settings)
        )
    finally:
        if acquired is not None:
            shutil.rmtree(acquired.scratch_dir, ignore_errors=True)


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
