"""Slack /analyze slash command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from shotlist.models import ShotList
from shotlist.jobs import JobError, JobRecord, JobStatus
from shotlist.api import create_app
from shotlist.render import render_markdown
from slack_sdk.errors import SlackApiError

from shotlist.slack_app import (
    SLACK_COMMAND_PATH,
    SLACK_RESPONSE_URL_TIMEOUT_SEC,
    SlackSettings,
    execute_slack_analyze,
    parse_analyze_url,
    post_response_url,
    upload_shot_list_files,
)

_TEST_SLACK = SlackSettings(
    bot_token="xoxb-test",
    signing_secret=None,
    app_token="xapp-test",
)


def test_parse_analyze_url_strips_whitespace() -> None:
    assert parse_analyze_url("  https://youtube.com/shorts/x  ") == (
        "https://youtube.com/shorts/x"
    )


def test_parse_analyze_url_empty_returns_none() -> None:
    assert parse_analyze_url("") is None
    assert parse_analyze_url("   ") is None


@pytest.mark.asyncio
async def test_post_response_url_sends_ephemeral() -> None:
    captured: list[dict] = []

    def _ok_response() -> httpx.Response:
        return httpx.Response(
            200,
            request=httpx.Request("POST", "https://hooks.slack.com/x"),
        )

    async def fake_post(
        _self: httpx.AsyncClient,
        _url: str,
        *,
        json: dict | None = None,
        **_: object,
    ) -> httpx.Response:
        captured.append(json or {})
        return _ok_response()

    with patch.object(httpx.AsyncClient, "post", fake_post):
        await post_response_url("https://hooks.slack.com/x", "hello")

    assert captured == [{"text": "hello", "response_type": "ephemeral"}]


@pytest.mark.asyncio
async def test_execute_slack_analyze_posts_rendered_shots(
    sample_shot_list: ShotList, tmp_path: Path
) -> None:
    out = tmp_path / "vid"
    out.mkdir()
    (out / "shot-list.json").write_text(
        sample_shot_list.model_dump_json(indent=2), encoding="utf-8"
    )
    (out / "shot-list.md").write_text(
        render_markdown(sample_shot_list), encoding="utf-8"
    )
    record = JobRecord(
        job_id="j1",
        status=JobStatus.COMPLETED,
        output_dir=out,
        video_id="vid",
    )
    posts: list[str] = []

    async def capture_post(
        url: str, text: str, *, blocks: list | None = None, ephemeral: bool = True
    ) -> None:
        posts.append(text)

    with patch("shotlist.slack_app.job_store.run_sync", new=AsyncMock(return_value=record)):
        with patch(
            "shotlist.slack_app.upload_shot_list_files", new=AsyncMock()
        ) as upload_mock:
            with patch("shotlist.slack_app.post_response_url", side_effect=capture_post):
                await execute_slack_analyze(
                    "https://www.youtube.com/shorts/abc",
                    "https://hooks.slack.com/x",
                    channel_id="C123",
                    slack_settings=_TEST_SLACK,
                )

    upload_mock.assert_awaited_once()
    assert len(posts) == 1
    assert "shot-list.md" in posts[0]


@pytest.mark.asyncio
async def test_upload_shot_list_files_falls_back_to_dm(
    sample_shot_list: ShotList, tmp_path: Path
) -> None:
    out = tmp_path
    (out / "shot-list.json").write_text(
        sample_shot_list.model_dump_json(indent=2), encoding="utf-8"
    )
    (out / "shot-list.md").write_text(
        render_markdown(sample_shot_list), encoding="utf-8"
    )
    posted: list[str] = []

    async def fake_post(
        _client: object, channel_id: str, _output_dir: Path, _shot_list: ShotList
    ) -> None:
        posted.append(channel_id)
        if channel_id == "CCHAN":
            raise SlackApiError(
                message="not in channel",
                response={"ok": False, "error": "not_in_channel"},
            )

    slack_client = AsyncMock()
    with patch("shotlist.slack_app.AsyncWebClient", return_value=slack_client):
        with patch("shotlist.slack_app._post_files_to_channel", side_effect=fake_post):
            with patch(
                "shotlist.slack_app._open_dm_channel",
                new=AsyncMock(return_value="D_DM"),
            ):
                landed = await upload_shot_list_files(
                    "CCHAN",
                    out,
                    sample_shot_list,
                    bot_token="xoxb-test",
                    user_id="U1",
                )

    assert landed == "D_DM"
    assert posted == ["CCHAN", "D_DM"]


@pytest.mark.asyncio
async def test_execute_slack_analyze_surfaces_job_error() -> None:
    record = JobRecord(
        job_id="j2",
        status=JobStatus.FAILED,
        error=JobError("invalid_video_url", "not a YouTube Short URL", 400),
    )
    posts: list[str] = []

    async def capture_post(url: str, text: str, *, ephemeral: bool = True) -> None:
        posts.append(text)

    with patch("shotlist.slack_app.job_store.run_sync", new=AsyncMock(return_value=record)):
        with patch("shotlist.slack_app.post_response_url", side_effect=capture_post):
            await execute_slack_analyze(
                "https://example.com/x",
                "https://hooks.slack.com/x",
                channel_id="C123",
                slack_settings=_TEST_SLACK,
            )

    assert posts == ["not a YouTube Short URL"]


@pytest.mark.asyncio
async def test_execute_slack_analyze_failed_without_error_object() -> None:
    record = JobRecord(job_id="j3", status=JobStatus.FAILED, error=None)
    posts: list[str] = []

    async def capture_post(url: str, text: str, *, ephemeral: bool = True) -> None:
        posts.append(text)

    with patch("shotlist.slack_app.job_store.run_sync", new=AsyncMock(return_value=record)):
        with patch("shotlist.slack_app.post_response_url", side_effect=capture_post):
            await execute_slack_analyze(
                "https://www.youtube.com/shorts/abc",
                "https://hooks.slack.com/x",
                channel_id="C123",
                slack_settings=_TEST_SLACK,
            )

    assert posts == ["Analysis failed."]


@pytest.mark.asyncio
async def test_execute_slack_analyze_posts_when_output_missing(
    tmp_path: Path,
) -> None:
    out = tmp_path / "vid"
    out.mkdir()
    record = JobRecord(
        job_id="j4",
        status=JobStatus.COMPLETED,
        output_dir=out,
        video_id="vid",
    )
    posts: list[str] = []

    async def capture_post(url: str, text: str, *, ephemeral: bool = True) -> None:
        posts.append(text)

    with patch("shotlist.slack_app.job_store.run_sync", new=AsyncMock(return_value=record)):
        with patch("shotlist.slack_app.post_response_url", side_effect=capture_post):
            await execute_slack_analyze(
                "https://www.youtube.com/shorts/abc",
                "https://hooks.slack.com/x",
                channel_id="C123",
                slack_settings=_TEST_SLACK,
            )

    assert len(posts) == 1
    assert posts[0].startswith("Analysis failed:")


@pytest.mark.asyncio
async def test_post_response_url_raises_on_http_error() -> None:
    async def fake_post(
        _self: httpx.AsyncClient,
        _url: str,
        **_: object,
    ) -> httpx.Response:
        return httpx.Response(
            500,
            request=httpx.Request("POST", "https://hooks.slack.com/x"),
        )

    with patch.object(httpx.AsyncClient, "post", fake_post):
        with pytest.raises(httpx.HTTPStatusError):
            await post_response_url("https://hooks.slack.com/x", "hello")


@pytest.mark.asyncio
async def test_post_response_url_uses_timeout() -> None:
    captured: dict[str, float] = {}

    class FakeAsyncClient:
        def __init__(self, timeout: float | httpx.Timeout | None = None) -> None:
            if isinstance(timeout, (int, float)):
                captured["timeout"] = float(timeout)

        async def __aenter__(self) -> FakeAsyncClient:
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def post(self, url: str, *, json: dict | None = None) -> httpx.Response:
            return httpx.Response(200, request=httpx.Request("POST", url))

    with patch("shotlist.slack_app.httpx.AsyncClient", FakeAsyncClient):
        await post_response_url("https://hooks.slack.com/x", "hello")

    assert captured["timeout"] == SLACK_RESPONSE_URL_TIMEOUT_SEC


def test_create_app_mounts_slack_commands_when_http_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "test-signing-secret")
    monkeypatch.delenv("SLACK_APP_TOKEN", raising=False)

    app = create_app()
    paths = {route.path for route in app.routes if hasattr(route, "path")}
    assert SLACK_COMMAND_PATH in paths


def test_slack_commands_rejects_unsigned_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fastapi.testclient import TestClient

    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "test-signing-secret")
    monkeypatch.delenv("SLACK_APP_TOKEN", raising=False)

    client = TestClient(create_app())
    response = client.post(
        SLACK_COMMAND_PATH,
        data={
            "token": "x",
            "team_id": "T",
            "team_domain": "test",
            "channel_id": "C",
            "channel_name": "general",
            "user_id": "U",
            "user_name": "user",
            "command": "/analyze",
            "text": "https://youtube.com/shorts/x",
            "response_url": "https://hooks.slack.com/x",
            "trigger_id": "133",
        },
    )
    assert response.status_code == 401
