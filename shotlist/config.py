"""Environment-backed settings for the analyze pipeline."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return float(raw)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return int(raw)


@dataclass(frozen=True)
class Settings:
    output_dir: Path
    vision_backend: str
    transcript_backend: str
    frame_interval_sec: float
    max_video_duration_sec: float
    frame_long_edge_px: int
    frame_jpeg_quality: int
    whisper_model: str
    whisper_compute_type: str
    pipeline_version: str


def get_settings() -> Settings:
    output = os.environ.get("OUTPUT_DIR", "./output")
    return Settings(
        output_dir=Path(output),
        vision_backend=os.environ.get("VISION_BACKEND", "openrouter").lower(),
        transcript_backend=os.environ.get("TRANSCRIPT_BACKEND", "whisper").lower(),
        frame_interval_sec=_env_float("FRAME_INTERVAL_SEC", 1.0),
        max_video_duration_sec=_env_float("MAX_VIDEO_DURATION_SEC", 90.0),
        frame_long_edge_px=_env_int("FRAME_LONG_EDGE_PX", 768),
        frame_jpeg_quality=_env_int("FRAME_JPEG_QUALITY", 85),
        whisper_model=os.environ.get("WHISPER_MODEL", "small"),
        whisper_compute_type=os.environ.get("WHISPER_COMPUTE_TYPE", "int8"),
        pipeline_version=os.environ.get("PIPELINE_VERSION", "0.1.0"),
    )
