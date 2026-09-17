"""Download public YouTube Shorts via yt-dlp into scratch storage."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from shotlist.config import Settings
from shotlist.errors import InvalidVideoUrlError, VideoTooLongError
from shotlist.models import VideoMetadata

_VIDEO_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")


@dataclass(frozen=True)
class AcquiredVideo:
    video_path: Path
    metadata: VideoMetadata
    scratch_dir: Path


def parse_youtube_video_id(url: str) -> str:
    """Extract an 11-character YouTube video id from a supported URL shape."""
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower().removeprefix("www.")
    path = parsed.path or ""

    if host in {"youtu.be"}:
        video_id = path.strip("/").split("/")[0]
    elif host in {"youtube.com", "m.youtube.com"}:
        if path.startswith("/shorts/"):
            video_id = path.removeprefix("/shorts/").split("/")[0]
        elif path == "/watch":
            qs = parse_qs(parsed.query)
            raw = qs.get("v", [None])[0]
            video_id = raw or ""
        else:
            video_id = ""
    else:
        video_id = ""

    if not video_id or not _VIDEO_ID_RE.match(video_id):
        raise InvalidVideoUrlError(f"not a supported YouTube video URL: {url}")
    return video_id


def validate_youtube_url(url: str) -> str:
    """Return video id or raise InvalidVideoUrlError."""
    if not url or not url.strip():
        raise InvalidVideoUrlError("empty URL")
    try:
        return parse_youtube_video_id(url)
    except InvalidVideoUrlError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise InvalidVideoUrlError(f"not a supported YouTube video URL: {url}") from exc


def metadata_from_info(info: dict) -> VideoMetadata:
    duration = info.get("duration")
    if duration is None:
        raise InvalidVideoUrlError("video metadata missing duration")
    return VideoMetadata(
        url=str(info.get("webpage_url") or info.get("original_url") or ""),
        video_id=str(info["id"]),
        title=str(info.get("title") or "Untitled"),
        channel=str(info.get("channel") or info.get("uploader") or "Unknown"),
        duration_sec=float(duration),
        thumbnail_url=info.get("thumbnail"),
        analyzed_at=datetime.now(timezone.utc),
    )


def _yt_dlp_info(url: str) -> dict:
    proc = subprocess.run(
        [
            "yt-dlp",
            "--no-playlist",
            "--no-warnings",
            "--dump-single-json",
            url,
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "yt-dlp failed").strip()
        raise InvalidVideoUrlError(detail)
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise InvalidVideoUrlError("yt-dlp returned invalid metadata") from exc


def _yt_dlp_download(url: str, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    template = str(out_path.with_suffix(".%(ext)s"))
    proc = subprocess.run(
        [
            "yt-dlp",
            "--no-playlist",
            "--no-warnings",
            "-f",
            "bv*+ba/b",
            "--merge-output-format",
            "mp4",
            "-o",
            template,
            url,
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "yt-dlp download failed").strip()
        raise InvalidVideoUrlError(detail)
    if not out_path.is_file():
        candidates = sorted(out_path.parent.glob("video.*"))
        if not candidates:
            raise InvalidVideoUrlError("yt-dlp did not produce a video file")
        if candidates[0] != out_path:
            candidates[0].rename(out_path)


def acquire_youtube_short(url: str, settings: Settings) -> AcquiredVideo:
    """
    Download a public YouTube Short into a per-job dir under ``settings.scratch_dir``.

    Raises InvalidVideoUrlError or VideoTooLongError before media prep runs.
    """
    normalized = url.strip()
    video_id = validate_youtube_url(normalized)
    scratch_root = settings.scratch_dir
    scratch_root.mkdir(parents=True, exist_ok=True)
    scratch_dir = Path(
        tempfile.mkdtemp(prefix=f"{video_id}-", dir=str(scratch_root))
    )

    try:
        info = _yt_dlp_info(normalized)
        metadata = metadata_from_info(info)
        if metadata.duration_sec > settings.max_video_duration_sec:
            raise VideoTooLongError(
                f"Video duration {metadata.duration_sec:.1f}s exceeds max "
                f"{settings.max_video_duration_sec}s"
            )

        video_path = scratch_dir / "video.mp4"
        _yt_dlp_download(normalized, video_path)

        return AcquiredVideo(
            video_path=video_path,
            metadata=metadata,
            scratch_dir=scratch_dir,
        )
    except Exception:
        shutil.rmtree(scratch_dir, ignore_errors=True)
        raise
