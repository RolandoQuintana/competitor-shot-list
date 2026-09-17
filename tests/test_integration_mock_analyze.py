"""End-to-end mock analyze on bundled fixture media (CI-safe)."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from shotlist.models import ShotList
from shotlist.pipeline import analyze_fixture, bundled_fixture_video_path
from shotlist.validation import validate_shot_list_structure

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_VIDEO = bundled_fixture_video_path()


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


@pytest.mark.integration
def test_mock_analyze_fixture_writes_artifacts(tmp_path, monkeypatch) -> None:
    if not FIXTURE_VIDEO.is_file():
        pytest.skip(f"missing bundled fixture video: {FIXTURE_VIDEO}")
    if not _ffmpeg_available():
        pytest.skip("ffmpeg/ffprobe not available")

    monkeypatch.setenv("VISION_BACKEND", "mock")
    monkeypatch.setenv("TRANSCRIPT_BACKEND", "stub")
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))

    out_dir = analyze_fixture()
    assert out_dir == tmp_path / "ci-sample"
    json_path = out_dir / "shot-list.json"
    md_path = out_dir / "shot-list.md"
    assert json_path.is_file()
    assert md_path.is_file()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    shot_list = ShotList.model_validate(payload)
    validate_shot_list_structure(shot_list)
    assert shot_list.shots
    assert "Full transcript" in md_path.read_text(encoding="utf-8")


@pytest.mark.integration
def test_cli_analyze_fixture_exits_zero(tmp_path, monkeypatch) -> None:
    if not FIXTURE_VIDEO.is_file():
        pytest.skip(f"missing bundled fixture video: {FIXTURE_VIDEO}")
    if not _ffmpeg_available():
        pytest.skip("ffmpeg/ffprobe not available")

    env = {
        **dict(__import__("os").environ),
        "VISION_BACKEND": "mock",
        "TRANSCRIPT_BACKEND": "stub",
        "OUTPUT_DIR": str(tmp_path),
    }
    result = subprocess.run(
        [sys.executable, "-m", "shotlist", "analyze", "--fixture"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "ci-sample" / "shot-list.json").is_file()
