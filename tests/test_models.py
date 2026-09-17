import pytest
from pydantic import ValidationError

from shotlist.models import SCHEMA_VERSION, Shot, ShotList, ShotType


def test_fixture_parses(sample_shot_list: ShotList) -> None:
    assert sample_shot_list.schema_version == SCHEMA_VERSION
    assert sample_shot_list.video.video_id == "abc123"
    assert len(sample_shot_list.shots) == 2
    assert sample_shot_list.shots[0].shot_type == ShotType.TALKING_HEAD


def test_shot_rejects_end_before_start() -> None:
    with pytest.raises(ValidationError):
        Shot(
            index=1,
            start_sec=5.0,
            end_sec=5.0,
            time_label="5s",
            shot_type=ShotType.OTHER,
            visual="x",
            dialogue="",
            on_screen_text="",
        )


def test_shot_type_enum_values() -> None:
    expected = {
        "talking_head",
        "pov",
        "b_roll",
        "screen_recording",
        "product_closeup",
        "text_card",
        "montage",
        "other",
    }
    assert {m.value for m in ShotType} == expected


def test_on_screen_text_null_becomes_empty_string(sample_shot_list_dict: dict) -> None:
    sample_shot_list_dict["shots"][0]["on_screen_text"] = None
    shot_list = ShotList.model_validate(sample_shot_list_dict)
    assert shot_list.shots[0].on_screen_text == ""


def test_wrong_schema_version_rejected(sample_shot_list_dict: dict) -> None:
    sample_shot_list_dict["schema_version"] = "2.0"
    with pytest.raises(ValidationError):
        ShotList.model_validate(sample_shot_list_dict)
