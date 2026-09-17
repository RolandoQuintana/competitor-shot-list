"""Audio transcription (Whisper or CI stub)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from shotlist.config import Settings


@dataclass(frozen=True)
class TranscriptResult:
    full_text: str
    segments: list[dict[str, float | str]]


def stub_transcript(duration_sec: float) -> TranscriptResult:
    """Deterministic transcript for fixture / CI runs (no model download)."""
    text = "Fixture short sample audio."
    return TranscriptResult(
        full_text=text,
        segments=[
            {"start_sec": 0.0, "end_sec": duration_sec, "text": text},
        ],
    )


def transcribe_audio(
    wav_path: Path, settings: Settings, *, duration_sec: float
) -> TranscriptResult:
    if settings.transcript_backend == "stub":
        return stub_transcript(duration_sec)

    from faster_whisper import WhisperModel

    model = WhisperModel(
        settings.whisper_model,
        device="cpu",
        compute_type=settings.whisper_compute_type,
    )
    segments_iter, _info = model.transcribe(str(wav_path), word_timestamps=False)
    segments: list[dict[str, float | str]] = []
    parts: list[str] = []
    for seg in segments_iter:
        text = seg.text.strip()
        if not text:
            continue
        segments.append(
            {"start_sec": float(seg.start), "end_sec": float(seg.end), "text": text}
        )
        parts.append(text)
    return TranscriptResult(full_text=" ".join(parts), segments=segments)


def dialogue_for_interval(
    segments: list[dict[str, float | str]], start_sec: float, end_sec: float
) -> str:
    chunks: list[str] = []
    for seg in segments:
        seg_start = float(seg["start_sec"])
        seg_end = float(seg["end_sec"])
        if seg_end <= start_sec or seg_start >= end_sec:
            continue
        chunks.append(str(seg["text"]))
    return " ".join(chunks).strip()
