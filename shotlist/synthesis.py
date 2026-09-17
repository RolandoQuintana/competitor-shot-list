"""Build schema-valid shot lists from media + vision output."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from shotlist.models import (
    Analysis,
    Framing,
    Role,
    Shot,
    ShotList,
    ShotType,
    Transcript,
    TranscriptSegment,
    VideoMetadata,
)
from shotlist.transcribe import TranscriptResult, dialogue_for_interval


def _time_label(start_sec: float, end_sec: float) -> str:
    if abs(start_sec - round(start_sec)) < 0.05 and abs(end_sec - round(end_sec)) < 0.05:
        return f"{int(round(start_sec))}–{int(round(end_sec))}s"
    return f"{start_sec:g}–{end_sec:g}s"


def _clean_visual(description: str) -> str:
    text = re.sub(r"^\[mock\]\s*", "", description).strip()
    return text or "Visual content"


def synthesize_shot_list(
    *,
    video: VideoMetadata,
    duration_sec: float,
    frame_interval_sec: float,
    vision_descriptions: list[str],
    transcript: TranscriptResult,
    pipeline_version: str,
    vision_error_count: int = 0,
) -> ShotList:
    """Mock/rule-based synthesis: one shot per extracted frame second."""
    if not vision_descriptions:
        raise ValueError("vision_descriptions must not be empty")

    shots: list[Shot] = []
    for index, vision in enumerate(vision_descriptions, start=1):
        start = (index - 1) * frame_interval_sec
        end = min(index * frame_interval_sec, duration_sec)
        if end <= start:
            end = min(start + frame_interval_sec, duration_sec)
        shots.append(
            Shot(
                index=index,
                start_sec=start,
                end_sec=end,
                time_label=_time_label(start, end),
                shot_type=ShotType.TALKING_HEAD if index == 1 else ShotType.B_ROLL,
                visual=_clean_visual(vision),
                dialogue=dialogue_for_interval(transcript.segments, start, end),
                on_screen_text="",
                framing=Framing.MEDIUM if index == 1 else None,
                role=Role.HOOK if index == 1 else Role.OTHER,
            )
        )

    if shots:
        last = shots[-1]
        if last.end_sec < duration_sec:
            shots[-1] = last.model_copy(
                update={
                    "end_sec": duration_sec,
                    "time_label": _time_label(last.start_sec, duration_sec),
                }
            )

    segments = [
        TranscriptSegment(
            start_sec=float(s["start_sec"]),
            end_sec=float(s["end_sec"]),
            text=str(s["text"]),
        )
        for s in transcript.segments
    ]

    return ShotList(
        video=video.model_copy(
            update={
                "duration_sec": duration_sec,
                "analyzed_at": datetime.now(timezone.utc),
            }
        ),
        analysis=Analysis(
            vision_error_count=vision_error_count,
            pipeline_version=pipeline_version,
            models={"vision_backend": "mock", "synthesis": "rule-based-mock"},
        ),
        transcript=Transcript(full_text=transcript.full_text, segments=segments or None),
        shots=shots,
    )
