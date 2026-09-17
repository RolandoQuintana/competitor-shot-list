"""Shared OpenRouter chat-completions client."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from shotlist.config import Settings


def openrouter_headers(settings: Settings) -> dict[str, str]:
    if not settings.openrouter_api_key:
        raise ValueError("OPENROUTER_API_KEY is required for OpenRouter requests")
    headers: dict[str, str] = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
    }
    if settings.openrouter_http_referer:
        headers["HTTP-Referer"] = settings.openrouter_http_referer
    if settings.openrouter_app_title:
        headers["X-Title"] = settings.openrouter_app_title
    return headers


async def post_chat_completions(
    settings: Settings,
    payload: dict[str, Any],
    *,
    timeout_sec: float = 120.0,
    max_retries: int = 8,
    delay_after_sec: float = 0.0,
) -> str:
    """POST /chat/completions and return assistant message content."""
    base = settings.openrouter_base_url.rstrip("/")
    headers = openrouter_headers(settings)
    last_err: str | None = None

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=timeout_sec) as client:
                resp = await client.post(
                    f"{base}/chat/completions",
                    json=payload,
                    headers=headers,
                )
            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After")
                wait = float(retry_after) if retry_after else min(2**attempt, 60)
                last_err = f"HTTP 429 rate limited (retry in {wait:.0f}s)"
                await asyncio.sleep(wait)
                continue
            if resp.status_code >= 400:
                last_err = f"HTTP {resp.status_code}: {resp.text[:300]}"
                resp.raise_for_status()
            data = resp.json()
            choice = (data.get("choices") or [{}])[0]
            message = choice.get("message") or {}
            text = (message.get("content") or "").strip()
            if delay_after_sec > 0:
                await asyncio.sleep(delay_after_sec)
            return text
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)
            await asyncio.sleep(min(2**attempt, 60))

    raise RuntimeError(last_err or "OpenRouter chat completion failed after retries")


async def chat_completion(
    settings: Settings,
    *,
    model: str,
    messages: list[dict[str, Any]],
    timeout_sec: float = 120.0,
    max_retries: int = 8,
) -> str:
    """Text chat completion."""
    payload = {"model": model, "messages": messages}
    return await post_chat_completions(
        settings,
        payload,
        timeout_sec=timeout_sec,
        max_retries=max_retries,
    )
