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
from shotlist.render import render_slack

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
    ephemeral: bool = True,
) -> None:
    body: dict[str, str] = {"text": text}
    if ephemeral:
        body["response_type"] = "ephemeral"
    async with httpx.AsyncClient(timeout=SLACK_RESPONSE_URL_TIMEOUT_SEC) as client:
        response = await client.post(response_url, json=body)
        response.raise_for_status()


async def execute_slack_analyze(
    url: str,
    response_url: str,
    *,
    settings: Settings | None = None,
) -> None:
    """Run the same analyze job as HTTP/CLI and post Slack mrkdwn to response_url."""
    try:
        settings = settings or get_settings()
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
        await post_response_url(response_url, render_slack(shot_list))
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
            execute_slack_analyze(url, response_url),
            name="slack-analyze",
        )

    return bolt


def mount_slack_on_fastapi(
    app: FastAPI,
    settings: SlackSettings,
) -> tuple[AsyncApp, AsyncSocketModeHandler | None]:
    """Register Bolt slash command on FastAPI (HTTP) and optional Socket Mode handler."""
    from slack_bolt.adapter.starlette.async_handler import AsyncSlackRequestHandler

    bolt_app = build_slack_bolt_app(settings)
    socket_handler: AsyncSocketModeHandler | None = None

    if settings.http_enabled:
        handler = AsyncSlackRequestHandler(bolt_app)

        @app.post(SLACK_COMMAND_PATH)
        async def slack_commands(request: Request) -> Any:
            return await handler.handle(request)

    if settings.socket_mode_enabled:
        from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

        socket_handler = AsyncSocketModeHandler(bolt_app, settings.app_token or "")

    return bolt_app, socket_handler


async def stop_socket_mode(handler: AsyncSocketModeHandler | None) -> None:
    if handler is None:
        return
    with suppress(Exception):
        await handler.close_async()
