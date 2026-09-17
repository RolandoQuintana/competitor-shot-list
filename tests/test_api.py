"""HTTP analyze API (FastAPI)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from shotlist.api import app
from shotlist.errors import InvalidVideoUrlError, VideoTooLongError


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_analyze_requires_url_or_fixture(client: TestClient) -> None:
    response = client.post("/analyze", json={})
    assert response.status_code == 422


def test_analyze_fixture_wait_returns_completed(client: TestClient, tmp_path: Path) -> None:
    out = tmp_path / "ci-sample"
    out.mkdir()

    with patch("shotlist.jobs.run_analyze_job", return_value=out):
        response = client.post(
            "/analyze",
            json={"fixture": True},
            params={"wait": "true"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["video_id"] == "ci-sample"
    assert body["output_dir"].endswith("ci-sample")


def test_analyze_async_returns_job_id(client: TestClient) -> None:
    with patch("shotlist.jobs.run_analyze_job", return_value=Path("/app/output/vid")):
        response = client.post(
            "/analyze",
            json={"fixture": True},
            params={"wait": "false"},
        )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    job_id = body["job_id"]
    assert job_id

    status = client.get(f"/jobs/{job_id}")
    assert status.status_code == 200
    assert status.json()["job_id"] == job_id


def test_job_not_found(client: TestClient) -> None:
    response = client.get("/jobs/does-not-exist")
    assert response.status_code == 404


def test_analyze_wait_surfaces_pipeline_error(client: TestClient) -> None:
    with patch(
        "shotlist.jobs.run_analyze_job",
        side_effect=InvalidVideoUrlError("not a YouTube Short URL"),
    ):
        response = client.post(
            "/analyze",
            json={"url": "https://example.com/x"},
            params={"wait": "true"},
        )

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "invalid_video_url"
    assert "YouTube" in body["error"]["message"]


def test_analyze_wait_video_too_long(client: TestClient) -> None:
    with patch(
        "shotlist.jobs.run_analyze_job",
        side_effect=VideoTooLongError("too long"),
    ):
        response = client.post(
            "/analyze",
            json={"url": "https://www.youtube.com/shorts/abc"},
            params={"wait": "true"},
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "video_too_long"
