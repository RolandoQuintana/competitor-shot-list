"""HTTP API integration: real mock analyze through FastAPI (CI-safe)."""

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from shotlist.api import app
from shotlist.models import ShotList
from shotlist.pipeline import bundled_fixture_video_path
from shotlist.validation import validate_shot_list_structure

FIXTURE_VIDEO = bundled_fixture_video_path()


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


@pytest.mark.integration
def test_api_analyze_fixture_wait_writes_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if not FIXTURE_VIDEO.is_file():
        pytest.skip(f"missing bundled fixture video: {FIXTURE_VIDEO}")
    if not _ffmpeg_available():
        pytest.skip("ffmpeg/ffprobe not available")

    monkeypatch.setenv("VISION_BACKEND", "mock")
    monkeypatch.setenv("TRANSCRIPT_BACKEND", "stub")
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))

    client = TestClient(app)
    response = client.post(
        "/analyze",
        json={"fixture": True},
        params={"wait": "true"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "completed"
    assert body["video_id"] == "ci-sample"
    assert body["output_dir"] == "ci-sample"

    out_dir = tmp_path / "ci-sample"
    json_path = out_dir / "shot-list.json"
    md_path = out_dir / "shot-list.md"
    assert json_path.is_file()
    assert md_path.is_file()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    shot_list = ShotList.model_validate(payload)
    validate_shot_list_structure(shot_list)
    assert shot_list.shots
    assert "Full transcript" in md_path.read_text(encoding="utf-8")
