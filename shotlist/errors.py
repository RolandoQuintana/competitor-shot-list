"""Pipeline-level errors."""


class PipelineError(RuntimeError):
    """Base class for analyze pipeline failures."""


class EmptyShotsError(PipelineError):
    """Raised when synthesis yields no shots (DIS-7)."""


class InvalidVideoUrlError(PipelineError):
    """URL is missing, malformed, or yt-dlp cannot fetch the video."""


class VideoTooLongError(PipelineError):
    """Video duration exceeds MAX_VIDEO_DURATION_SEC."""


class JobTimeoutError(PipelineError):
    """Analyze job exceeded JOB_TIMEOUT_SEC."""


class SynthesisError(PipelineError):
    """LLM synthesis or JSON structuring failed after retries."""
