"""Pipeline-level errors."""

from __future__ import annotations

from typing import ClassVar


class PipelineError(RuntimeError):
    """Base class for analyze pipeline failures."""

    api_code: ClassVar[str] = "pipeline_error"
    http_status: ClassVar[int] = 422


class EmptyShotsError(PipelineError):
    """Raised when synthesis yields no shots (DIS-7)."""

    api_code = "empty_shots"


class InvalidVideoUrlError(PipelineError):
    """URL is missing, malformed, or yt-dlp cannot fetch the video."""

    api_code = "invalid_video_url"
    http_status = 400


class VideoTooLongError(PipelineError):
    """Video duration exceeds MAX_VIDEO_DURATION_SEC."""

    api_code = "video_too_long"
    http_status = 400


class JobTimeoutError(PipelineError):
    """Analyze job exceeded JOB_TIMEOUT_SEC."""

    api_code = "job_timeout"


class SynthesisError(PipelineError):
    """LLM synthesis or JSON structuring failed after retries."""

    api_code = "synthesis_error"


class MissingOpenRouterApiKeyError(PipelineError):
    """OPENROUTER_API_KEY required for the configured vision backend."""

    api_code = "missing_openrouter_api_key"
    http_status = 400
