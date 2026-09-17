"""CLI entry point (python -m shotlist)."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_shotlist(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "shotlist", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_help_exits_zero_and_shows_usage() -> None:
    result = run_shotlist("--help")
    assert result.returncode == 0
    assert "usage" in result.stdout.lower() or "Usage" in result.stdout


def test_version_exits_zero() -> None:
    result = run_shotlist("--version")
    assert result.returncode == 0
    assert "0.1.0" in result.stdout
