"""Build schema-valid shot lists from media + vision output."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from shotlist.config import Settings
from shotlist.errors import SynthesisError
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
from shotlist.openrouter import chat_completion
from shotlist.transcribe import TranscriptResult, dialogue_for_interval
from shotlist.validation import validate_shot_list_structure


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


_SHOT_TYPE_VALUES = ", ".join(sorted(t.value for t in ShotType))
_FRAMING_VALUES = ", ".join(sorted(f.value for f in Framing))
_ROLE_VALUES = ", ".join(sorted(r.value for r in Role))


def _transcript_block(transcript: TranscriptResult) -> str:
    lines = [f"Full transcript: {transcript.full_text}"]
    for seg in transcript.segments:
        lines.append(
            f"  [{seg['start_sec']:g}s–{seg['end_sec']:g}s] {seg['text']}"
        )
    return "\n".join(lines)


def _vision_timeline(
    vision_descriptions: list[str],
    frame_interval_sec: float,
    duration_sec: float,
) -> str:
    lines: list[str] = []
    for i, desc in enumerate(vision_descriptions):
        start = i * frame_interval_sec
        end = min((i + 1) * frame_interval_sec, duration_sec)
        lines.append(f"  [{start:g}s–{end:g}s] {desc}")
    return "\n".join(lines)


def _synthesis_system_prompt() -> str:
    return (
        "You are a video editor assistant. Given per-second vision notes and a transcript, "
        "produce a production-oriented shot list as JSON.\n"
        "Return ONLY valid JSON with a single top-level key \"shots\" (array). "
        "Each shot object must include: index (1-based contiguous), start_sec, end_sec, "
        "time_label (e.g. \"0–5s\"), shot_type, visual, dialogue, on_screen_text "
        "(string, empty if none). Optional: framing, camera_movement, role, notes.\n"
        f"shot_type one of: {_SHOT_TYPE_VALUES}.\n"
        f"framing one of: {_FRAMING_VALUES}.\n"
        f"role one of: {_ROLE_VALUES}.\n"
        "Shots must be chronological, non-overlapping, span the full video duration, "
        "and use contiguous indices starting at 1."
    )


def extract_json_object(text: str) -> dict[str, Any]:
    """Pull a JSON object from model output (strip optional markdown fences)."""
    stripped = text.strip()
    fence = re.match(r"^```(?:json)?\s*\n?(.*)\n?```\s*$", stripped, re.DOTALL)
    if fence:
        stripped = fence.group(1).strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise json.JSONDecodeError("no JSON object found", stripped, 0)
    return json.loads(stripped[start : end + 1])


def _shot_list_from_synthesis_payload(
    *,
    video: VideoMetadata,
    duration_sec: float,
    transcript: TranscriptResult,
    payload: dict[str, Any],
    pipeline_version: str,
    vision_error_count: int,
    settings: Settings,
) -> ShotList:
    raw_shots = payload.get("shots")
    if not isinstance(raw_shots, list) or not raw_shots:
        raise SynthesisError("synthesis JSON missing non-empty shots[]")

    segments = [
        TranscriptSegment(
            start_sec=float(s["start_sec"]),
            end_sec=float(s["end_sec"]),
            text=str(s["text"]),
        )
        for s in transcript.segments
    ]

    shots = [Shot.model_validate(item) for item in raw_shots]
    shot_list = ShotList(
        video=video.model_copy(
            update={
                "duration_sec": duration_sec,
                "analyzed_at": datetime.now(timezone.utc),
            }
        ),
        analysis=Analysis(
            vision_error_count=vision_error_count,
            pipeline_version=pipeline_version,
            models={
                "vision": settings.openrouter_vision_model,
                "synthesis": settings.openrouter_synthesis_model,
                "transcription": settings.openrouter_transcription_model,
                "transcript_backend": settings.transcript_backend,
            },
        ),
        transcript=Transcript(full_text=transcript.full_text, segments=segments or None),
        shots=shots,
    )
    validate_shot_list_structure(shot_list)
    return shot_list


async def synthesize_shot_list_openrouter(
    *,
    settings: Settings,
    video: VideoMetadata,
    duration_sec: float,
    frame_interval_sec: float,
    vision_descriptions: list[str],
    transcript: TranscriptResult,
    pipeline_version: str,
    vision_error_count: int = 0,
) -> ShotList:
    """LLM synthesis via OpenRouter with JSON parse / repair retries."""
    if not vision_descriptions:
        raise ValueError("vision_descriptions must not be empty")

    user_content = (
        f"Video title: {video.title}\n"
        f"Channel: {video.channel}\n"
        f"Duration (seconds): {duration_sec:g}\n\n"
        f"{_transcript_block(transcript)}\n\n"
        "Per-frame vision (approximate timestamps):\n"
        f"{_vision_timeline(vision_descriptions, frame_interval_sec, duration_sec)}"
    )
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _synthesis_system_prompt()},
        {"role": "user", "content": user_content},
    ]

    last_error = ""
    raw_response = ""
    for attempt in range(settings.synthesis_max_retries):
        try:
            raw_response = await chat_completion(
                settings,
                model=settings.openrouter_synthesis_model,
                messages=messages,
                max_retries=3,
            )
            payload = extract_json_object(raw_response)
            return _shot_list_from_synthesis_payload(
                video=video,
                duration_sec=duration_sec,
                transcript=transcript,
                payload=payload,
                pipeline_version=pipeline_version,
                vision_error_count=vision_error_count,
                settings=settings,
            )
        except (json.JSONDecodeError, ValidationError, SynthesisError, ValueError) as exc:
            last_error = str(exc)
            messages = [
                {"role": "system", "content": _synthesis_system_prompt()},
                {"role": "user", "content": user_content},
                {"role": "assistant", "content": raw_response},
                {
                    "role": "user",
                    "content": (
                        "Your previous response was invalid. Fix it and return ONLY valid JSON "
                        f"with a \"shots\" array. Error: {last_error}"
                    ),
                },
            ]

    raise SynthesisError(
        f"synthesis failed after {settings.synthesis_max_retries} attempts: {last_error}"
    )
