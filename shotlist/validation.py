"""Structural validation beyond Pydantic field checks."""

from __future__ import annotations

from shotlist.models import ShotList

SPAN_TOLERANCE_SEC = 1.0


class ShotListStructureError(ValueError):
    """Raised when shots fail structural rules (overlap, span)."""


def validate_shot_list_structure(shot_list: ShotList) -> None:
    """Ensure shots are non-overlapping and span the video within tolerance."""
    shots = shot_list.shots
    duration = shot_list.video.duration_sec

    if not shots:
        raise ShotListStructureError("shots must not be empty")

    for i, shot in enumerate(shots):
        if i > 0 and shot.start_sec < shots[i - 1].start_sec:
            raise ShotListStructureError(
                "shots must be ordered by start_sec (chronological)"
            )

    for i, shot in enumerate(shots):
        if shot.index != i + 1:
            raise ShotListStructureError(
                f"shot index must be 1-based contiguous; expected {i + 1}, got {shot.index}"
            )

    for prev, curr in zip(shots, shots[1:], strict=False):
        if curr.start_sec < prev.end_sec:
            raise ShotListStructureError(
                f"shots overlap: shot {prev.index} ends at {prev.end_sec}s "
                f"but shot {curr.index} starts at {curr.start_sec}s"
            )

    first = shots[0]
    last = shots[-1]

    if first.start_sec > SPAN_TOLERANCE_SEC:
        raise ShotListStructureError(
            f"first shot must start within {SPAN_TOLERANCE_SEC}s of video start; "
            f"got start_sec={first.start_sec}"
        )

    if last.end_sec < duration - SPAN_TOLERANCE_SEC:
        raise ShotListStructureError(
            f"last shot must end within {SPAN_TOLERANCE_SEC}s of video end "
            f"({duration}s); got end_sec={last.end_sec}"
        )

    if last.end_sec > duration + SPAN_TOLERANCE_SEC:
        raise ShotListStructureError(
            f"last shot end_sec must not exceed duration by more than "
            f"{SPAN_TOLERANCE_SEC}s; duration={duration}, end_sec={last.end_sec}"
        )
