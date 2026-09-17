"""Human-readable Markdown and Slack mrkdwn renderers."""

from __future__ import annotations

from datetime import timezone

from shotlist.models import Shot, ShotList

SLACK_SHOT_CAP = 12
_SLACK_MORE_SUFFIX = "_+{n} more — see shot-list in output/_"

# Max cell widths for monospace table (Slack section text limit is 3000 chars).
_SLACK_COL_WIDTHS = {
    "time": 7,
    "shot": 22,
    "visual": 36,
    "dialogue": 24,
    "osd": 28,
}


def _shot_column(shot: Shot) -> str:
    parts = [shot.shot_type.value]
    if shot.framing is not None:
        parts.append(shot.framing.value)
    if shot.camera_movement is not None:
        parts.append(shot.camera_movement.value)
    if shot.role is not None:
        parts.append(shot.role.value)
    return " · ".join(parts)


def _format_dialogue(dialogue: str) -> str:
    return dialogue if dialogue else "—"


def _format_osd(on_screen_text: str | None) -> str:
    text = on_screen_text or ""
    return text if text else "—"


def render_markdown(shot_list: ShotList) -> str:
    """Render shot-list.md content (header, table, full transcript)."""
    v = shot_list.video
    analyzed = v.analyzed_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"# {v.title}",
        "",
        f"**Channel:** {v.channel}  ",
        f"**URL:** {v.url}  ",
        f"**Duration:** {v.duration_sec:g}s  ",
        f"**Analyzed:** {analyzed}",
        "",
        "| Time | Shot | Visual | Dialogue | On-screen text |",
        "| --- | --- | --- | --- | --- |",
    ]

    for shot in shot_list.shots:
        lines.append(
            "| {time} | {shot_col} | {visual} | {dialogue} | {osd} |".format(
                time=shot.time_label,
                shot_col=_shot_column(shot),
                visual=shot.visual.replace("|", "\\|"),
                dialogue=_format_dialogue(shot.dialogue).replace("|", "\\|"),
                osd=_format_osd(shot.on_screen_text).replace("|", "\\|"),
            )
        )

    lines.extend(
        [
            "",
            "## Full transcript",
            "",
            shot_list.transcript.full_text,
            "",
        ]
    )
    return "\n".join(lines)


def _truncate_cell(text: str, width: int) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= width:
        return cleaned.ljust(width)
    if width <= 1:
        return cleaned[:width]
    return (cleaned[: width - 1] + "…").ljust(width)


def _slack_table_row(shot: Shot) -> str:
    cols = _SLACK_COL_WIDTHS
    return " | ".join(
        [
            _truncate_cell(shot.time_label, cols["time"]),
            _truncate_cell(_shot_column(shot), cols["shot"]),
            _truncate_cell(shot.visual, cols["visual"]),
            _truncate_cell(_format_dialogue(shot.dialogue), cols["dialogue"]),
            _truncate_cell(_format_osd(shot.on_screen_text), cols["osd"]),
        ]
    )


def _slack_table_header() -> str:
    cols = _SLACK_COL_WIDTHS
    return " | ".join(
        [
            _truncate_cell("Time", cols["time"]),
            _truncate_cell("Shot", cols["shot"]),
            _truncate_cell("Visual", cols["visual"]),
            _truncate_cell("Dialogue", cols["dialogue"]),
            _truncate_cell("On-screen", cols["osd"]),
        ]
    )


def _slack_table_divider() -> str:
    return "-+-".join("-" * w for w in _SLACK_COL_WIDTHS.values())


def render_slack_table(shot_list: ShotList, *, max_shots: int = SLACK_SHOT_CAP) -> str:
    """Monospace shot table for Slack code blocks."""
    shown = shot_list.shots[:max_shots]
    lines = [_slack_table_header(), _slack_table_divider()]
    lines.extend(_slack_table_row(s) for s in shown)
    remaining = len(shot_list.shots) - len(shown)
    if remaining > 0:
        lines.append("")
        lines.append(f"+{remaining} more shots — see shot-list.json in output/")
    return "\n".join(lines)


def render_slack_blocks(
    shot_list: ShotList, *, max_shots: int = SLACK_SHOT_CAP
) -> tuple[str, list[dict]]:
    """Block Kit payload: header, metadata, and a monospace table."""
    v = shot_list.video
    shown = shot_list.shots[:max_shots]
    fallback = f"Shot list: {v.title} ({len(shown)} shots)"
    table = render_slack_table(shot_list, max_shots=max_shots)

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": v.title[:150], "emoji": True},
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": (
                        f"*{v.channel}* · {v.duration_sec:g}s · "
                        f"<{v.url}|YouTube>"
                    ),
                }
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"```\n{table}\n```"},
        },
    ]
    transcript = shot_list.transcript.full_text.strip()
    if transcript:
        preview = transcript if len(transcript) <= 280 else transcript[:277] + "…"
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Transcript*\n>{preview.replace(chr(10), chr(10) + '>')}",
                },
            }
        )
    return fallback, blocks


def render_slack(shot_list: ShotList, *, max_shots: int = SLACK_SHOT_CAP) -> str:
    """Plain-text fallback (table in a code fence) for Slack notifications."""
    v = shot_list.video
    table = render_slack_table(shot_list, max_shots=max_shots)
    return f"*{v.title}*\n{v.channel} · {v.duration_sec:g}s\n\n```\n{table}\n```"
