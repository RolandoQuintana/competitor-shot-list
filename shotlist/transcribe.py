"""Audio transcription (OpenRouter STT, local Whisper, or CI stub)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shotlist.config import Settings
from shotlist.errors import TranscriptionError
from shotlist.openrouter import post_audio_transcription

_SUPPORTED_BACKENDS = frozenset({"stub", "whisper", "openrouter"})


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


def _transcribe_whisper_local(
    wav_path: Path, settings: Settings
) -> TranscriptResult:
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


def _segment_bounds(seg: dict[str, Any]) -> tuple[float, float]:
    start = seg.get("start_sec", seg.get("start"))
    end = seg.get("end_sec", seg.get("end"))
    if start is None or end is None:
        raise TranscriptionError("OpenRouter STT segment missing start/end timestamps")
    return float(start), float(end)


def transcript_from_verbose_json(data: dict[str, Any]) -> TranscriptResult:
    """Map OpenRouter / OpenAI verbose_json STT into TranscriptResult."""
    full_text = str(data.get("text") or "").strip()
    segments: list[dict[str, float | str]] = []
    for raw in data.get("segments") or []:
        if not isinstance(raw, dict):
            continue
        text = str(raw.get("text") or "").strip()
        if not text:
            continue
        start_sec, end_sec = _segment_bounds(raw)
        segments.append(
            {"start_sec": start_sec, "end_sec": end_sec, "text": text},
        )
    if not full_text and segments:
        full_text = " ".join(str(s["text"]) for s in segments)
    if full_text and not segments:
        raise TranscriptionError(
            "OpenRouter STT returned transcript text without timestamped segments"
        )
    return TranscriptResult(full_text=full_text, segments=segments)


async def _transcribe_openrouter(
    wav_path: Path, settings: Settings
) -> TranscriptResult:
    try:
        data = await post_audio_transcription(
            settings,
            wav_path,
            max_retries=settings.transcription_max_retries,
        )
    except RuntimeError as exc:
        raise TranscriptionError(str(exc)) from exc
    return transcript_from_verbose_json(data)


async def transcribe_audio(
    wav_path: Path, settings: Settings, *, duration_sec: float
) -> TranscriptResult:
    backend = settings.transcript_backend
    if backend not in _SUPPORTED_BACKENDS:
        raise ValueError(
            f"Unsupported TRANSCRIPT_BACKEND={backend!r}; "
            f"use one of {sorted(_SUPPORTED_BACKENDS)}"
        )
    if backend == "stub":
        return stub_transcript(duration_sec)
    if backend == "whisper":
        return await asyncio.to_thread(_transcribe_whisper_local, wav_path, settings)
    return await _transcribe_openrouter(wav_path, settings)


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
