from datetime import datetime, timezone

import pytest

from shotlist.models import VideoMetadata
from shotlist.synthesis import synthesize_shot_list
from shotlist.transcribe import TranscriptResult
from shotlist.validation import validate_shot_list_structure


def _video(duration: float) -> VideoMetadata:
    return VideoMetadata(
        url="fixture://ci-sample",
        video_id="ci-sample",
        title="CI Sample Short",
        channel="Fixture",
        duration_sec=duration,
        analyzed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def test_mock_synthesis_produces_valid_structure() -> None:
    duration = 3.0
    vision = ["[mock] frame one", "[mock] frame two", "[mock] frame three"]
    transcript = TranscriptResult(
        full_text="Fixture short sample audio.",
        segments=[{"start_sec": 0.0, "end_sec": 3.0, "text": "Fixture short sample audio."}],
    )
    shot_list = synthesize_shot_list(
        video=_video(duration),
        duration_sec=duration,
        frame_interval_sec=1.0,
        vision_descriptions=vision,
        transcript=transcript,
        pipeline_version="0.1.0",
    )
    validate_shot_list_structure(shot_list)
    assert len(shot_list.shots) == 3
    assert shot_list.shots[-1].end_sec == duration


def test_synthesis_rejects_empty_vision() -> None:
    with pytest.raises(ValueError, match="vision_descriptions"):
        synthesize_shot_list(
            video=_video(1.0),
            duration_sec=1.0,
            frame_interval_sec=1.0,
            vision_descriptions=[],
            transcript=TranscriptResult(full_text="", segments=[]),
            pipeline_version="0.1.0",
        )
