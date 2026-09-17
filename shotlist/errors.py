"""Pipeline-level errors."""


class PipelineError(RuntimeError):
    """Base class for analyze pipeline failures."""


class EmptyShotsError(PipelineError):
    """Raised when synthesis yields no shots (DIS-7)."""
