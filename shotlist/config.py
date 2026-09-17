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
    scratch_dir: Path
    vision_backend: str
    transcript_backend: str
    frame_interval_sec: float
    max_video_duration_sec: float
    frame_long_edge_px: int
    frame_jpeg_quality: int
    whisper_model: str
    whisper_compute_type: str
    pipeline_version: str
    openrouter_api_key: str | None
    openrouter_base_url: str
    openrouter_vision_model: str
    openrouter_synthesis_model: str
    openrouter_transcription_model: str
    openrouter_http_referer: str | None
    openrouter_app_title: str
    transcription_max_retries: int
    vision_prompt: str
    vision_request_delay_sec: float
    vision_max_retries: int
    vision_concurrency: int
    synthesis_max_retries: int
    job_timeout_sec: float


def get_settings() -> Settings:
    output = os.environ.get("OUTPUT_DIR", "./output")
    scratch = os.environ.get("SCRATCH_DIR", "/tmp/shotlist")
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip() or None
    referer = os.environ.get("OPENROUTER_HTTP_REFERER", "").strip() or None
    return Settings(
        output_dir=Path(output),
        scratch_dir=Path(scratch),
        vision_backend=os.environ.get("VISION_BACKEND", "openrouter").lower(),
        transcript_backend=os.environ.get("TRANSCRIPT_BACKEND", "openrouter").lower(),
        frame_interval_sec=_env_float("FRAME_INTERVAL_SEC", 1.0),
        max_video_duration_sec=_env_float("MAX_VIDEO_DURATION_SEC", 55.0),
        frame_long_edge_px=_env_int("FRAME_LONG_EDGE_PX", 768),
        frame_jpeg_quality=_env_int("FRAME_JPEG_QUALITY", 85),
        whisper_model=os.environ.get("WHISPER_MODEL", "small"),
        whisper_compute_type=os.environ.get("WHISPER_COMPUTE_TYPE", "int8"),
        pipeline_version=os.environ.get("PIPELINE_VERSION", "0.1.0"),
        openrouter_api_key=api_key,
        openrouter_base_url=os.environ.get(
            "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        ),
        openrouter_vision_model=os.environ.get(
            "OPENROUTER_VISION_MODEL", "deepseek/deepseek-v4-flash-vision-exp"
        ),
        openrouter_synthesis_model=os.environ.get(
            "OPENROUTER_SYNTHESIS_MODEL", "openai/gpt-4o-mini"
        ),
        openrouter_transcription_model=os.environ.get(
            "OPENROUTER_TRANSCRIPTION_MODEL", "openai/whisper-large-v3"
        ),
        openrouter_http_referer=referer,
        openrouter_app_title=os.environ.get(
            "OPENROUTER_APP_TITLE", "competitor-shot-list"
        ),
        vision_prompt=os.environ.get(
            "VISION_PROMPT",
            "Describe what is happening visually in this video frame. "
            "List any on-screen text exactly as shown. Be concise (2–4 sentences).",
        ),
        vision_request_delay_sec=_env_float("VISION_REQUEST_DELAY_SEC", 2.0),
        vision_max_retries=_env_int("VISION_MAX_RETRIES", 8),
        vision_concurrency=_env_int("VISION_CONCURRENCY", 1),
        synthesis_max_retries=_env_int("SYNTHESIS_MAX_RETRIES", 3),
        transcription_max_retries=_env_int("TRANSCRIPTION_MAX_RETRIES", 8),
        job_timeout_sec=_env_float("JOB_TIMEOUT_SEC", 1800.0),
    )
