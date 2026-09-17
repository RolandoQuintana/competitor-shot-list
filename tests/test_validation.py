from datetime import datetime, timezone

import pytest

from shotlist.models import Shot, ShotList, ShotType, Transcript, VideoMetadata
from shotlist.validation import ShotListStructureError, validate_shot_list_structure


def _video(duration: float = 30.0) -> VideoMetadata:
    return VideoMetadata(
        url="https://www.youtube.com/shorts/v",
        video_id="v",
        title="T",
        channel="C",
        duration_sec=duration,
        analyzed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def test_valid_structure_passes(sample_shot_list: ShotList) -> None:
    validate_shot_list_structure(sample_shot_list)


def test_overlapping_shots_rejected() -> None:
    shot_list = ShotList(
        video=_video(30),
        transcript=Transcript(full_text=""),
        shots=[
            Shot(
                index=1,
                start_sec=0.0,
                end_sec=20.0,
                time_label="0–20s",
                shot_type=ShotType.B_ROLL,
                visual="a",
                dialogue="",
                on_screen_text="",
            ),
            Shot(
                index=2,
                start_sec=15.0,
                end_sec=30.0,
                time_label="15–30s",
                shot_type=ShotType.B_ROLL,
                visual="b",
                dialogue="",
                on_screen_text="",
            ),
        ],
    )
    with pytest.raises(ShotListStructureError, match="overlap"):
        validate_shot_list_structure(shot_list)


def test_span_too_short_at_end_rejected() -> None:
    shot_list = ShotList(
        video=_video(30),
        transcript=Transcript(full_text=""),
        shots=[
            Shot(
                index=1,
                start_sec=0.0,
                end_sec=25.0,
                time_label="0–25s",
                shot_type=ShotType.B_ROLL,
                visual="a",
                dialogue="",
                on_screen_text="",
            ),
        ],
    )
    with pytest.raises(ShotListStructureError, match="within 1.0s of video end"):
        validate_shot_list_structure(shot_list)


def test_span_within_one_second_tolerance() -> None:
    shot_list = ShotList(
        video=_video(30),
        transcript=Transcript(full_text=""),
        shots=[
            Shot(
                index=1,
                start_sec=0.5,
                end_sec=29.2,
                time_label="0.5–29.2s",
                shot_type=ShotType.B_ROLL,
                visual="a",
                dialogue="",
                on_screen_text="",
            ),
        ],
    )
    validate_shot_list_structure(shot_list)


def test_empty_shots_rejected() -> None:
    shot_list = ShotList(
        video=_video(),
        transcript=Transcript(full_text=""),
        shots=[],
    )
    with pytest.raises(ShotListStructureError, match="empty"):
        validate_shot_list_structure(shot_list)
