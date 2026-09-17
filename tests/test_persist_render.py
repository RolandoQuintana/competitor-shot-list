import json
from datetime import datetime, timezone
from pathlib import Path

from shotlist.models import Shot, ShotList, ShotType, Transcript, VideoMetadata
from shotlist.persist import persist_shot_list
from shotlist.render import render_slack


def test_persist_writes_json_and_markdown(
    sample_shot_list: ShotList, tmp_path: Path
) -> None:
    out = persist_shot_list(sample_shot_list, tmp_path)
    assert out == tmp_path / "abc123"
    assert (out / "shot-list.json").is_file()
    assert (out / "shot-list.md").is_file()

    loaded = json.loads((out / "shot-list.json").read_text(encoding="utf-8"))
    assert loaded["schema_version"] == "1.0"
    assert loaded["video"]["video_id"] == "abc123"

    md = (out / "shot-list.md").read_text(encoding="utf-8")
    assert "## Full transcript" in md
    assert "Hello world. This is a test short." in md
    assert "| Time | Shot | Visual |" in md


def test_slack_renderer_caps_at_twelve_shots() -> None:
    shots = [
        Shot(
            index=i,
            start_sec=float(i),
            end_sec=float(i + 1),
            time_label=f"{i}–{i + 1}s",
            shot_type=ShotType.B_ROLL,
            visual=f"visual {i}",
            dialogue="",
            on_screen_text="",
        )
        for i in range(1, 16)
    ]
    shot_list = ShotList(
        video=VideoMetadata(
            url="https://www.youtube.com/shorts/long",
            video_id="long",
            title="Long",
            channel="C",
            duration_sec=16.0,
            analyzed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ),
        transcript=Transcript(full_text=""),
        shots=shots,
    )
    text = render_slack(shot_list)
    bullet_lines = [ln for ln in text.splitlines() if ln.startswith("•")]
    assert len(bullet_lines) == 12
    assert "_+3 more — see shot-list in output/_" in text


def test_slack_under_cap_no_suffix(minimal_shot_list: ShotList) -> None:
    text = render_slack(minimal_shot_list)
    assert "more — see shot-list" not in text
    assert "Shot 1" in text
