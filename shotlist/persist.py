"""Write shot list artifacts to ./output/<video-id>/."""

from __future__ import annotations

import json
from pathlib import Path

from shotlist.models import ShotList
from shotlist.render import render_markdown
from shotlist.validation import validate_shot_list_structure


def output_dir_for_video(base_dir: Path, video_id: str) -> Path:
    if not video_id or video_id in {".", ".."} or "/" in video_id or "\\" in video_id:
        raise ValueError(f"invalid video_id for output path: {video_id!r}")
    out = (base_dir / video_id).resolve()
    base_resolved = base_dir.resolve()
    if not out.is_relative_to(base_resolved):
        raise ValueError(f"video_id escapes output directory: {video_id!r}")
    return out


def persist_shot_list(
    shot_list: ShotList,
    base_dir: Path,
    *,
    validate: bool = True,
) -> Path:
    """
    Write shot-list.json and shot-list.md under base_dir/<video_id>/.

    Returns the video output directory path.
    """
    if validate:
        validate_shot_list_structure(shot_list)

    out = output_dir_for_video(base_dir, shot_list.video.video_id)
    out.mkdir(parents=True, exist_ok=True)

    json_path = out / "shot-list.json"
    md_path = out / "shot-list.md"

    payload = shot_list.model_dump(mode="json")
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(render_markdown(shot_list), encoding="utf-8")

    return out
