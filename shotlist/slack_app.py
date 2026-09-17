"""Optional Slack /analyze slash command (Bolt + same job store as HTTP)."""

from __future__ import annotations

import asyncio
import json
import os
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
from starlette.requests import Request

from shotlist.config import Settings, get_settings
from shotlist.jobs import AnalyzeJobRequest, JobStatus, job_store
from shotlist.models import ShotList
from slack_sdk.web.async_client import AsyncWebClient

if TYPE_CHECKING:
    from fastapi import FastAPI
    from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
    from slack_bolt.async_app import AsyncApp

SLACK_COMMAND_PATH = "/slack/commands"
SLACK_RESPONSE_URL_TIMEOUT_SEC = 30.0


@dataclass(frozen=True)
class SlackSettings:
    bot_token: str
    signing_secret: str | None
    app_token: str | None

    @property
    def http_enabled(self) -> bool:
        return self.signing_secret is not None

    @property
    def socket_mode_enabled(self) -> bool:
        return self.app_token is not None


def get_slack_settings() -> SlackSettings | None:
    bot_token = os.environ.get("SLACK_BOT_TOKEN", "").strip()
    if not bot_token:
        return None
    signing_secret = os.environ.get("SLACK_SIGNING_SECRET", "").strip() or None
    app_token = os.environ.get("SLACK_APP_TOKEN", "").strip() or None
    if signing_secret is None and app_token is None:
        return None
    return SlackSettings(
        bot_token=bot_token,
        signing_secret=signing_secret,
        app_token=app_token,
    )


def parse_analyze_url(text: str) -> str | None:
    stripped = (text or "").strip()
    return stripped if stripped else None


def load_shot_list_from_output(output_dir: Path) -> ShotList:
    path = output_dir / "shot-list.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return ShotList.model_validate(payload)


async def post_response_url(
    response_url: str,
    text: str,
    *,
    blocks: list[dict] | None = None,
    ephemeral: bool = True,
) -> None:
    body: dict[str, object] = {"text": text}
    if blocks is not None:
        body["blocks"] = blocks
    if ephemeral:
        body["response_type"] = "ephemeral"
    async with httpx.AsyncClient(timeout=SLACK_RESPONSE_URL_TIMEOUT_SEC) as client:
        response = await client.post(response_url, json=body)
        response.raise_for_status()


async def upload_shot_list_files(
    channel_id: str,
    output_dir: Path,
    shot_list: ShotList,
    *,
    bot_token: str,
) -> None:
    """Share shot-list.md and shot-list.json in the channel where /analyze was run."""
    md_path = output_dir / "shot-list.md"
    json_path = output_dir / "shot-list.json"
    if not md_path.is_file() or not json_path.is_file():
        raise FileNotFoundError("shot-list artifacts missing on disk")

    title = shot_list.video.title
    comment = (
        f"Shot list for *{title}* · {shot_list.video.channel} · "
        f"{shot_list.video.duration_sec:g}s · <{shot_list.video.url}|YouTube>"
    )
    client = AsyncWebClient(token=bot_token)
    await client.files_upload_v2(
        channel=channel_id,
        initial_comment=comment,
        file_uploads=[
            {"file": str(md_path), "filename": md_path.name, "title": md_path.name},
            {
                "file": str(json_path),
                "filename": json_path.name,
                "title": json_path.name,
            },
        ],
    )


async def execute_slack_analyze(
    url: str,
    response_url: str,
    *,
    channel_id: str,
    settings: Settings | None = None,
    slack_settings: SlackSettings | None = None,
) -> None:
    """Run the same analyze job as HTTP/CLI; upload artifacts and confirm via response_url."""
    try:
        settings = settings or get_settings()
        slack_settings = slack_settings or get_slack_settings()
        if slack_settings is None:
            await post_response_url(response_url, "Slack bot token is not configured.")
            return

        request = AnalyzeJobRequest(url=url, fixture=False, settings=settings)
        record = await job_store.run_sync(request)
        if record.status == JobStatus.FAILED:
            message = (
                record.error.message if record.error is not None else "Analysis failed."
            )
            await post_response_url(response_url, message)
            return
        if record.output_dir is None:
            await post_response_url(
                response_url, "Analysis finished without output."
            )
            return
        shot_list = load_shot_list_from_output(record.output_dir)
        await upload_shot_list_files(
            channel_id,
            record.output_dir,
            shot_list,
            bot_token=slack_settings.bot_token,
        )
        await post_response_url(
            response_url,
            (
                f"Done — posted `shot-list.md` and `shot-list.json` for "
                f"*{shot_list.video.title}* in this channel."
            ),
        )
    except Exception as exc:  # noqa: BLE001
        await post_response_url(response_url, f"Analysis failed: {exc}")


def build_slack_bolt_app(settings: SlackSettings) -> AsyncApp:
    from slack_bolt.async_app import AsyncApp

    kwargs: dict[str, str] = {"token": settings.bot_token}
    if settings.signing_secret is not None:
        kwargs["signing_secret"] = settings.signing_secret
    bolt = AsyncApp(**kwargs)

    @bolt.command("/analyze")
    async def analyze_command(ack: Any, command: dict[str, Any]) -> None:
        url = parse_analyze_url(command.get("text", ""))
        response_url = command["response_url"]
        if url is None:
            await ack(
                text="Usage: `/analyze <youtube-short-url>`",
                response_type="ephemeral",
            )
            return
        await ack(
            text="Analyzing video… This may take a few minutes.",
            response_type="ephemeral",
        )
        asyncio.create_task(
            execute_slack_analyze(
                url,
                response_url,
                channel_id=command["channel_id"],
                slack_settings=settings,
            ),
            name="slack-analyze",
        )

    return bolt


def mount_slack_on_fastapi(app: FastAPI, settings: SlackSettings) -> None:
    """Register Bolt slash command on FastAPI (HTTP). Socket Mode starts in lifespan."""
    from slack_bolt.adapter.starlette.async_handler import AsyncSlackRequestHandler

    bolt_app = build_slack_bolt_app(settings)
    app.state.slack_bolt_app = bolt_app
    app.state.slack_socket_enabled = settings.socket_mode_enabled
    app.state.slack_app_token = settings.app_token

    if settings.http_enabled:
        handler = AsyncSlackRequestHandler(bolt_app)

        @app.post(SLACK_COMMAND_PATH)
        async def slack_commands(request: Request) -> Any:
            return await handler.handle(request)


def create_slack_socket_handler(app: FastAPI) -> AsyncSocketModeHandler | None:
    """Build Socket Mode handler once an asyncio event loop is running."""
    if not getattr(app.state, "slack_socket_enabled", False):
        return None
    from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

    bolt_app = app.state.slack_bolt_app
    app_token = getattr(app.state, "slack_app_token", None) or ""
    return AsyncSocketModeHandler(bolt_app, app_token)


async def stop_socket_mode(handler: AsyncSocketModeHandler | None) -> None:
    if handler is None:
        return
    with suppress(Exception):
        await handler.close_async()
