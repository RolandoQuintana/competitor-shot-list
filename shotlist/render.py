"""Human-readable Markdown and Slack mrkdwn renderers."""

from __future__ import annotations

from datetime import timezone

from shotlist.models import Shot, ShotList

SLACK_SHOT_CAP = 12
_SLACK_MORE_SUFFIX = "_+{n} more — see shot-list in output/_"


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


def _slack_shot_line(shot: Shot) -> str:
    osd = shot.on_screen_text or ""
    osd_part = f" · OSD: {osd}" if osd else ""
    dialogue = shot.dialogue or ""
    return (
        f"• *Shot {shot.index} ({shot.time_label})* · {shot.shot_type.value} · "
        f"{shot.visual} · {dialogue}{osd_part}"
    )


def render_slack(shot_list: ShotList, *, max_shots: int = SLACK_SHOT_CAP) -> str:
    """Render Slack mrkdwn bullet list with optional shot cap."""
    shown = shot_list.shots[:max_shots]
    lines = [_slack_shot_line(s) for s in shown]
    remaining = len(shot_list.shots) - len(shown)
    if remaining > 0:
        lines.append(_SLACK_MORE_SUFFIX.format(n=remaining))
    return "\n".join(lines)
