"""Pillow-based renderer for LoL notifications — team logo cards + text fallback."""

from __future__ import annotations

import asyncio
import io
import tempfile
from datetime import date
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont

from .formatter.message import (
    format_daily_schedule,
    format_match_bp,
    format_match_detail,
    format_match_result,
    format_pre_match_alert,
    format_schedule,
    format_standings,
)
from .models import LeagueMatch, MatchDetail, StandingEntry

_renderer_config: dict = {}
_logo_cache: dict[str, Image.Image] = {}
_logo_lock = asyncio.Lock()

# ── 字体 ──
_FONT_TITLE: ImageFont.FreeTypeFont | None = None
_FONT_BODY: ImageFont.FreeTypeFont | None = None
_FONT_LEAGUE: ImageFont.FreeTypeFont | None = None
_FONT_TEAM: ImageFont.FreeTypeFont | None = None
_FONT_TIME: ImageFont.FreeTypeFont | None = None
_fonts_loaded = False


def _load_fonts() -> None:
    global _FONT_TITLE, _FONT_BODY, _FONT_LEAGUE, _FONT_TEAM, _FONT_TIME, _fonts_loaded
    if _fonts_loaded:
        return

    # 中文字体候选（Windows → macOS → Linux → 项目内置）
    _CJK_CANDIDATES = [
        "msyh.ttc", "msyh.ttf",                          # Microsoft YaHei
        "simhei.ttf",                                     # SimHei
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    ]
    _EN_CANDIDATES = [
        "Orbitron-Bold.ttf",
        "assets/fonts/Orbitron-Bold.ttf",
        "Orbitron-Regular.ttf",
        "assets/fonts/Orbitron-Regular.ttf",
        "arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]

    def _try_load(candidates: list[str], size: int) -> ImageFont.FreeTypeFont:
        for name in candidates:
            try:
                return ImageFont.truetype(name, size)
            except (OSError, IOError):
                continue
        return ImageFont.load_default()

    _FONT_TITLE = _try_load(_EN_CANDIDATES, 40)
    _FONT_LEAGUE = _try_load(_EN_CANDIDATES + _CJK_CANDIDATES, 28)
    _FONT_TEAM = _try_load(_CJK_CANDIDATES + _EN_CANDIDATES, 26)
    _FONT_TIME = _try_load(_CJK_CANDIDATES + _EN_CANDIDATES, 22)
    _FONT_BODY = _try_load(_CJK_CANDIDATES, 20)
    _fonts_loaded = True


def configure(config) -> None:
    global _renderer_config
    _renderer_config = config or {}
    _load_fonts()


# ── 队标下载 ──

async def _download_logo(url: str) -> Image.Image | None:
    """下载队标图片并缓存（RGBA 格式）。"""
    if not url:
        return None
    async with _logo_lock:
        if url in _logo_cache:
            return _logo_cache[url].copy()

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; AstrBot/1.0)",
            })
            resp.raise_for_status()
            img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
            async with _logo_lock:
                _logo_cache[url] = img
            return img.copy()
    except Exception:
        return None


def _circle_crop(img: Image.Image, size: int) -> Image.Image:
    """将图片裁剪为圆形。"""
    img = img.resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size, size), fill=255)
    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(img, (0, 0), mask)
    return result


# ── 卡片渲染 ──

_CARD_W = 1200
_BG_DARK = (20, 20, 30)
_BG_HEADER = (30, 30, 48)
_BG_MATCH_ROW = (36, 36, 56)
_TEXT_WHITE = (240, 240, 240)
_TEXT_SUB = (180, 180, 200)
_ACCENT_GOLD = (255, 200, 50)
_ACCENT_BLUE = (80, 160, 255)
_ACCENT_RED = (255, 80, 80)


def _save_image(img: Image.Image) -> str:
    fd, path = tempfile.mkstemp(suffix=".png")
    Path(path).write_bytes(b"")
    img.save(path, format="PNG")
    return path


def _draw_centered_text(
    draw: ImageDraw.Draw,
    text: str,
    center_x: int,
    y: int,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int],
) -> int:
    """居中绘制文字，返回底部 y 坐标。"""
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    draw.text((center_x - w // 2, y), text, fill=fill, font=font)
    return y + h


# ── 每日赛程卡片（带队标） ──

async def render_daily_schedule(matches: list[LeagueMatch]) -> str:
    """渲染每日赛程：带双方队标、队名、联赛、时间的精美卡片。"""
    _load_fonts()
    if not matches:
        return _render_text_only_card("📅 今日无赛程", "好好休息一下吧~")

    today_str = date.today().strftime("%Y-%m-%d")

    # 预先按联赛分组
    by_league: dict[str, list[LeagueMatch]] = {}
    for m in matches:
        lg = m.league or "Unknown"
        by_league.setdefault(lg, []).append(m)

    # 预下载所有队标
    logo_tasks: dict[str, asyncio.Task] = {}
    for m in matches:
        for url in (m.team_images or []):
            if url and url not in logo_tasks:
                logo_tasks[url] = asyncio.create_task(_download_logo(url))
    # 等待所有下载完成
    logo_results: dict[str, Image.Image | None] = {}
    for url, task in logo_tasks.items():
        try:
            logo_results[url] = await task
        except Exception:
            logo_results[url] = None

    # 计算卡片高度
    logo_size = 90
    row_h = 140
    header_h = 100
    league_header_h = 44
    padding_bottom = 30

    total_rows = sum(len(v) for v in by_league.values())
    league_count = len(by_league)
    height = header_h + league_count * league_header_h + total_rows * row_h + padding_bottom

    img = Image.new("RGB", (_CARD_W, height), _BG_DARK)
    draw = ImageDraw.Draw(img)

    # ── 顶部标题栏 ──
    draw.rectangle((0, 0, _CARD_W, header_h), fill=_BG_HEADER)
    # 左侧装饰线
    draw.rectangle((20, 24, 24, 76), fill=_ACCENT_GOLD)
    _draw_centered_text(draw, "TODAY'S MATCHES", _CARD_W // 2, 16, _FONT_TITLE, _TEXT_WHITE)
    _draw_centered_text(draw, today_str, _CARD_W // 2, 60, _FONT_TIME, _TEXT_SUB)

    y = header_h

    for league_name, league_matches in by_league.items():
        # ── 联赛分隔标题 ──
        draw.rectangle((0, y, _CARD_W, y + league_header_h), fill=_BG_HEADER)
        _draw_centered_text(draw, league_name.upper(), _CARD_W // 2, y + 10, _FONT_LEAGUE, _ACCENT_GOLD)
        y += league_header_h

        for match in league_matches:
            draw.rectangle((20, y + 8, _CARD_W - 20, y + row_h - 8), fill=_BG_MATCH_ROW)

            teams = match.teams if match.teams else ["TBD", "TBD"]
            logos = match.team_images if match.team_images else []
            team_a = teams[0] if len(teams) > 0 else "TBD"
            team_b = teams[1] if len(teams) > 1 else "TBD"
            logo_a_url = logos[0] if len(logos) > 0 else ""
            logo_b_url = logos[1] if len(logos) > 1 else ""

            # ── 左队标 ──
            left_center_x = 240
            logo_y = y + (row_h - logo_size) // 2
            logo_a = logo_results.get(logo_a_url) if logo_a_url else None
            if logo_a:
                circled = _circle_crop(logo_a, logo_size)
                # 队标外圈
                draw.ellipse(
                    (left_center_x - logo_size // 2 - 3, logo_y - 3,
                     left_center_x + logo_size // 2 + 3, logo_y + logo_size + 3),
                    fill=_ACCENT_GOLD,
                )
                img.paste(circled, (left_center_x - logo_size // 2, logo_y), circled)
            else:
                # 无队标 — 占位圆
                cx, cy = left_center_x, logo_y + logo_size // 2
                draw.ellipse(
                    (cx - logo_size // 2, cy - logo_size // 2,
                     cx + logo_size // 2, cy + logo_size // 2),
                    outline=_TEXT_SUB, width=2,
                )
                draw.text((cx - 12, cy - 14), "?", fill=_TEXT_SUB, font=_FONT_TEAM)

            # 左队名
            team_a_display = team_a[:12]
            _draw_centered_text(draw, team_a_display, left_center_x, logo_y + logo_size + 4,
                                _FONT_TEAM, _TEXT_WHITE)

            # ── VS ──
            vs_x = _CARD_W // 2
            vs_y = y + row_h // 2 - 16
            _draw_centered_text(draw, "VS", vs_x, vs_y, _FONT_TITLE, _ACCENT_GOLD)

            # ── 右队标 ──
            right_center_x = _CARD_W - 240
            logo_b = logo_results.get(logo_b_url) if logo_b_url else None
            if logo_b:
                circled = _circle_crop(logo_b, logo_size)
                draw.ellipse(
                    (right_center_x - logo_size // 2 - 3, logo_y - 3,
                     right_center_x + logo_size // 2 + 3, logo_y + logo_size + 3),
                    fill=_ACCENT_GOLD,
                )
                img.paste(circled, (right_center_x - logo_size // 2, logo_y), circled)
            else:
                cx, cy = right_center_x, logo_y + logo_size // 2
                draw.ellipse(
                    (cx - logo_size // 2, cy - logo_size // 2,
                     cx + logo_size // 2, cy + logo_size // 2),
                    outline=_TEXT_SUB, width=2,
                )
                draw.text((cx - 12, cy - 14), "?", fill=_TEXT_SUB, font=_FONT_TEAM)

            # 右队名
            team_b_display = team_b[:12]
            _draw_centered_text(draw, team_b_display, right_center_x, logo_y + logo_size + 4,
                                _FONT_TEAM, _TEXT_WHITE)

            # ── 时间 & BO ──
            time_str = f"⏰ {match.start_time}"
            if match.bo_type:
                time_str += f"  |  {match.bo_type}"
            status = match.status
            if status in ("live", "in_progress"):
                time_str = "🔴 LIVE NOW  |  " + time_str
            _draw_centered_text(draw, time_str, vs_x, vs_y + 42, _FONT_TIME, _TEXT_SUB)

            y += row_h

    return _save_image(img)


# ── 赛前预告卡片 ──

async def render_pre_match_alert(match: LeagueMatch) -> str:
    """渲染赛前 10 分钟预告卡片。"""
    _load_fonts()

    teams = " vs ".join(match.teams) if match.teams else "未知对局"
    league = match.league or ""

    # 下载队标
    logo_a_url = match.team_images[0] if len(match.team_images) > 0 else ""
    logo_b_url = match.team_images[1] if len(match.team_images) > 1 else ""
    logo_a, logo_b = None, None
    if logo_a_url:
        logo_a = await _download_logo(logo_a_url)
    if logo_b_url:
        logo_b = await _download_logo(logo_b_url)

    width, height = 800, 400
    img = Image.new("RGB", (width, height), _BG_DARK)
    draw = ImageDraw.Draw(img)

    # 顶部渐变条
    for i in range(80):
        r = 30 + i * 2
        g = 30 + i
        b = 48 + i * 2
        draw.rectangle((0, i, width, i + 1), fill=(min(r, 255), min(g, 255), min(b, 255)))

    _draw_centered_text(draw, "⚡ 比赛即将开始！", width // 2, 30, _FONT_TITLE, _ACCENT_GOLD)
    _draw_centered_text(draw, league.upper(), width // 2, 90, _FONT_LEAGUE, _TEXT_WHITE)

    # 队标
    logo_size = 110
    lx, rx = 250, width - 250
    ly = 150

    if logo_a:
        circled = _circle_crop(logo_a, logo_size)
        img.paste(circled, (lx - logo_size // 2, ly), circled)
    else:
        draw.text((lx - 30, ly + logo_size // 2 - 20), match.teams[0][:6] if match.teams else "?",
                  fill=_TEXT_WHITE, font=_FONT_TEAM)

    # VS
    _draw_centered_text(draw, "VS", width // 2, ly + logo_size // 2 - 20, _FONT_TITLE, _ACCENT_GOLD)

    if logo_b:
        circled = _circle_crop(logo_b, logo_size)
        img.paste(circled, (rx - logo_size // 2, ly), circled)
    else:
        draw.text((rx - 30, ly + logo_size // 2 - 20), match.teams[1][:6] if len(match.teams) > 1 else "?",
                  fill=_TEXT_WHITE, font=_FONT_TEAM)

    # 时间
    time_str = f"⏰ {match.start_time} 开赛"
    if match.bo_type:
        time_str += f"  |  {match.bo_type}"
    _draw_centered_text(draw, time_str, width // 2, ly + logo_size + 30, _FONT_TIME, _TEXT_SUB)

    draw.rectangle((0, height - 3, width, height), fill=_ACCENT_GOLD)
    return _save_image(img)


# ── 纯文字卡片（回退用） ──

def _render_text_only_card(title: str, body: str) -> str:
    lines = body.splitlines()
    width = 800
    row_h = 30
    height = max(200, 120 + len(lines) * row_h)
    img = Image.new("RGB", (width, height), _BG_DARK)
    draw = ImageDraw.Draw(img)
    _load_fonts()
    draw.rectangle((0, 0, width, 80), fill=_BG_HEADER)
    draw.text((32, 22), title, fill=_TEXT_WHITE, font=_FONT_TITLE)
    y = 110
    for line in lines:
        draw.text((32, y), line, fill=_TEXT_SUB, font=_FONT_BODY)
        y += row_h
    return _save_image(img)


# ── 旧式 _render_card（保留兼容） ──

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
    w = 1200
    h = max(320, 120 + len(lines) * 28)
    image = Image.new("RGB", (w, h), _BG_DARK)
    draw = ImageDraw.Draw(image)
    _load_fonts()
    draw.rectangle((0, 0, w, 84), fill=_BG_HEADER)
    draw.rectangle((0, 84, w, 86), fill=_ACCENT_GOLD)
    draw.text((32, 22), title, fill=_TEXT_WHITE, font=_FONT_TITLE)
    y = 120
    for line in lines:
        draw.text((32, y), line, fill=_TEXT_SUB, font=_FONT_BODY)
        y += 28
    return _save_image(image)


# ── 旧式渲染（保持兼容） ──

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

