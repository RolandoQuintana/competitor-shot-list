"""OpenRouter speech-to-text (HTTP mocked)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from shotlist.config import Settings, get_settings
from shotlist.errors import TranscriptionError
from shotlist.transcribe import (
    TranscriptResult,
    stub_transcript,
    transcript_from_verbose_json,
    transcribe_audio,
)


def _settings(**overrides: object) -> Settings:
    base = replace(
        get_settings(),
        openrouter_api_key="test-key",
        transcript_backend="openrouter",
        transcription_max_retries=2,
    )
    return replace(base, **overrides) if overrides else base


def test_stub_transcript() -> None:
    result = stub_transcript(3.0)
    assert result.full_text
    assert len(result.segments) == 1


def test_transcript_from_verbose_json_maps_segments() -> None:
    result = transcript_from_verbose_json(
        {
            "text": "hello world",
            "segments": [
                {"start": 0.0, "end": 1.2, "text": "hello"},
                {"start": 1.2, "end": 2.0, "text": "world"},
            ],
        }
    )
    assert result.full_text == "hello world"
    assert result.segments[0]["start_sec"] == 0.0
    assert result.segments[1]["text"] == "world"


def test_transcript_from_verbose_json_empty_is_allowed() -> None:
    result = transcript_from_verbose_json({"text": "", "segments": []})
    assert result.full_text == ""
    assert result.segments == []


def test_transcript_from_verbose_json_text_without_segments_fails() -> None:
    with pytest.raises(TranscriptionError, match="without timestamped segments"):
        transcript_from_verbose_json({"text": "ghost words", "segments": []})


@pytest.mark.asyncio
async def test_transcribe_openrouter_calls_api(tmp_path: Path) -> None:
    wav = tmp_path / "audio.wav"
    wav.write_bytes(b"fake-wav")
    verbose = {
        "text": "spoken line",
        "segments": [{"start": 0.0, "end": 1.5, "text": "spoken line"}],
    }
    settings = _settings()

    with patch(
        "shotlist.transcribe.post_audio_transcription",
        new=AsyncMock(return_value=verbose),
    ) as mock_post:
        result = await transcribe_audio(wav, settings, duration_sec=1.5)

    assert isinstance(result, TranscriptResult)
    assert result.full_text == "spoken line"
    mock_post.assert_awaited_once_with(
        settings,
        wav,
        max_retries=settings.transcription_max_retries,
    )


@pytest.mark.asyncio
async def test_transcribe_openrouter_http_failure(tmp_path: Path) -> None:
    wav = tmp_path / "audio.wav"
    wav.write_bytes(b"fake-wav")

    with patch(
        "shotlist.transcribe.post_audio_transcription",
        new=AsyncMock(side_effect=RuntimeError("HTTP 500")),
    ):
        with pytest.raises(TranscriptionError, match="HTTP 500"):
            await transcribe_audio(wav, _settings(), duration_sec=1.0)


@pytest.mark.asyncio
async def test_transcribe_unknown_backend(tmp_path: Path) -> None:
    wav = tmp_path / "audio.wav"
    wav.write_bytes(b"x")
    settings = _settings(transcript_backend="invalid")

    with pytest.raises(ValueError, match="Unsupported TRANSCRIPT_BACKEND"):
        await transcribe_audio(wav, settings, duration_sec=1.0)
