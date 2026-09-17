"""FFmpeg media extraction (audio + frames)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"Command failed ({proc.returncode}): {' '.join(cmd)}\n"
            f"{proc.stderr or proc.stdout}"
        )


def probe_duration(video_path: Path) -> float:
    out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(out.stdout)
    return float(data["format"]["duration"])


def extract_audio(video_path: Path, wav_path: Path) -> None:
    _run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(wav_path),
        ]
    )


def extract_frames(
    video_path: Path,
    frames_dir: Path,
    *,
    interval_sec: float,
    long_edge: int,
    jpeg_quality: int,
    max_duration: float,
) -> list[Path]:
    frames_dir.mkdir(parents=True, exist_ok=True)
    fps = 1.0 / interval_sec if interval_sec > 0 else 1.0
    scale = (
        f"scale='if(gt(iw,ih),{long_edge},-2)':'if(gt(iw,ih),-2,{long_edge})'"
    )
    q = str(max(2, min(31, int((100 - jpeg_quality) / 3))))
    _run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-t",
            str(max_duration),
            "-vf",
            f"fps={fps},{scale}",
            "-q:v",
            q,
            str(frames_dir / "frame_%04d.jpg"),
        ]
    )
    return sorted(frames_dir.glob("frame_*.jpg"))
