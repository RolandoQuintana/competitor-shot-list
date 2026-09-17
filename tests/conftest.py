import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from shotlist.models import (
    Analysis,
    Shot,
    ShotList,
    ShotType,
    Transcript,
    VideoMetadata,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_shot_list_dict() -> dict:
    return json.loads((FIXTURES / "sample_shot_list.json").read_text(encoding="utf-8"))


@pytest.fixture
def sample_shot_list(sample_shot_list_dict: dict) -> ShotList:
    return ShotList.model_validate(sample_shot_list_dict)


@pytest.fixture
def minimal_shot_list() -> ShotList:
    return ShotList(
        video=VideoMetadata(
            url="https://www.youtube.com/shorts/x",
            video_id="x",
            title="T",
            channel="C",
            duration_sec=10.0,
            analyzed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ),
        transcript=Transcript(full_text="Hi"),
        shots=[
            Shot(
                index=1,
                start_sec=0.0,
                end_sec=10.0,
                time_label="0–10s",
                shot_type=ShotType.TALKING_HEAD,
                visual="v",
                dialogue="Hi",
                on_screen_text="",
            )
        ],
        analysis=Analysis(),
    )
