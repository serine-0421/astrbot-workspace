"""Simple Pillow-based renderer for LoL notifications."""

from __future__ import annotations

import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .formatter.message import format_match_bp, format_match_detail, format_match_result, format_schedule, format_standings, format_daily_schedule, format_pre_match_alert
from .models import LeagueMatch, MatchDetail, StandingEntry


_renderer_config: dict = {}


def configure(config) -> None:
    global _renderer_config
    _renderer_config = config or {}


def _wrap_lines(text: str, width: int = 34) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines():
        if not raw:
            lines.append("")
            continue
        current = raw
        while len(current) > width:
            lines.append(current[:width])
            current = current[width:]
        lines.append(current)
    return lines


def _render_card(title: str, body: str) -> str:
    lines = _wrap_lines(body)
    width = 1200
    height = max(320, 120 + len(lines) * 28)
    image = Image.new("RGB", (width, height), (18, 18, 26))
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arial.ttf", 24)
        body_font = ImageFont.truetype("arial.ttf", 18)
    except Exception:
        font = ImageFont.load_default()
        body_font = ImageFont.load_default()
    draw.rectangle((0, 0, width, 84), fill=(30, 30, 44))
    draw.text((32, 26), title, fill=(255, 255, 255), font=font)
    y = 120
    for line in lines:
        draw.text((32, y), line, fill=(220, 220, 220), font=body_font)
        y += 28
    fd, path = tempfile.mkstemp(suffix=".png")
    Path(path).write_bytes(b"")
    image.save(path, format="PNG")
    return path


async def render_schedule(matches: list[LeagueMatch], limit: int = 5) -> str:
    return _render_card("LOL SCHEDULE", format_schedule(matches, limit))


async def render_match_result(match: LeagueMatch) -> str:
    return _render_card("LOL RESULT", format_match_result(match))


async def render_match_bp(match: LeagueMatch) -> str:
    return _render_card("LOL BP", format_match_bp(match))


async def render_match_detail(detail: MatchDetail) -> str:
    return _render_card("LOL DETAIL", format_match_detail(detail))


async def render_standings(standings: list[StandingEntry]) -> str:
    return _render_card("LOL STANDINGS", format_standings(standings))


async def render_daily_schedule(matches: list[LeagueMatch]) -> str:
    """渲染每日赛程卡片（带队标尝试）。"""
    return _render_card("LOL TODAY", format_daily_schedule(matches))


async def render_pre_match_alert(match: LeagueMatch) -> str:
    """渲染赛前预告卡片。"""
    return _render_card("LOL PRE-MATCH", format_pre_match_alert(match))
