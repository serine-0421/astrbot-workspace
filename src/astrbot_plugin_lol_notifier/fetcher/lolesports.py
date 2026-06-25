"""LoL Esports 数据抓取器 — citoapi 封装。

数据来源：citoapi (https://api.citoapi.com/api/v1)

端点映射（旧 Riot API → 新 citoapi）：
  赛程:    getSchedule          → GET /lol/leagues/{slug}/schedule
  排名:    getStandings         → GET /lol/leagues/{slug}/standings
  实时:    getLive              → GET /lol/live
  详情:    getEventDetails      → GET /lol/matches/{matchId}
  实时帧:  feed.lolesports.com  → GET /lol/live/games/{gameId}/window
"""

from __future__ import annotations

import asyncio
import time
import traceback
from datetime import datetime
from typing import Any

import httpx

from astrbot.api import logger

from ..models import (
    BPEntry,
    Failure,
    JsonListResult,
    JsonResult,
    LeaderboardEntry,
    LeagueMatch,
    LiveGameFrame,
    LiveMatch,
    LiveResult,
    MatchDetail,
    MatchGame,
    ScheduleResult,
    StandingEntry,
    StandingsResult,
    Success,
)

# ── 常量 ──

_BASE_URL = "https://api.citoapi.com/api/v1"

_CITOAPI_KEY = "cito_dc5cfcfa4b9aca180e71c0e1282be83ef2bfc7658b9658ee5c88813fb6163091"

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

# ── citoapi League slug 映射 ──
_LEAGUE_SLUGS: dict[str, str] = {
    "lck": "lol-lck",
    "lpl": "lol-lpl",
    "lec": "lol-lec",
    "lcs": "lol-lcs",
    "lco": "lol-lco",
    "lcl": "lol-lcl",
    "ljl": "lol-ljl",
    "pcs": "lol-pcs",
    "vcs": "lol-vcs",
    "cblol": "lol-cblol",
    "lla": "lol-lla",
    "tcl": "lol-tcl",
    "msi": "lol-msi",
    "worlds": "lol-worlds",
}


def supported_leagues() -> list[str]:
    return sorted(_LEAGUE_SLUGS.keys())


def _cito_slug(user_slug: str) -> str:
    return _LEAGUE_SLUGS.get(user_slug.strip().lower(), "")


def _resolve_tournament_slug(raw: str) -> str:
    """将用户输入的锦标赛 ID 解析为 citoapi 使用的 slug。

    例如 "worlds2025" → 尝试多种格式直到匹配。
    如果都不匹配，返回原始输入。
    """
    raw = raw.strip()
    # 尝试直接使用
    if raw in _LEAGUE_SLUGS:
        return _LEAGUE_SLUGS[raw]

    # 尝试分离已知 league 基础名 + 年份
    import re
    m = re.match(r'^([a-zA-Z]+)(\d{4})$', raw)
    if m:
        base = m.group(1).lower()
        year = m.group(2)
        if base in _LEAGUE_SLUGS:
            cito = _LEAGUE_SLUGS[base]
            # lol-worlds → lol-worlds-2025
            return f"{cito}-{year}"
        # 尝试直接添加 lol- 前缀
        return f"lol-{base}-{year}"

    # 已有 lol- 前缀的就直接用
    if raw.startswith("lol-"):
        return raw

    return raw


def _user_slug_from_cito(cito_slug: str) -> str:
    for us, cs in _LEAGUE_SLUGS.items():
        if cs == cito_slug:
            return us.upper()
    return cito_slug.upper()


# ── API Key 管理（硬编码 + 运行时覆盖） ──

_runtime_key: str = ""


def get_api_key() -> str:
    import os
    env = os.environ.get("CITO_API_KEY", "").strip()
    if env:
        return env
    if _runtime_key:
        return _runtime_key
    return _CITOAPI_KEY


def set_api_key(key: str) -> None:
    global _runtime_key
    _runtime_key = key.strip()
    _reset_client()


# ── HTTP Client ──

_client: httpx.AsyncClient | None = None
_client_key_hash: str = ""


def _reset_client() -> None:
    global _client, _client_key_hash
    _client_key_hash = ""


async def close_session() -> None:
    global _client
    if _client:
        await _client.aclose()
        _client = None
        _client_key_hash = ""


async def _get_client() -> httpx.AsyncClient:
    global _client, _client_key_hash
    key = get_api_key()
    if _client is None or _client_key_hash != key:
        if _client:
            await _client.aclose()
        _client = httpx.AsyncClient(
            timeout=20.0,
            headers={
                "User-Agent": _USER_AGENT,
                "Accept": "application/json",
                "x-api-key": key,
            },
        )
        _client_key_hash = key
    return _client


# ── 速率限制 ──

# 每分钟 10 次限额 → 安全速率: 每次调用至少间隔 6 秒
_MIN_REQUEST_INTERVAL: float = 6.0
_last_request_time: float = 0.0
_rate_lock = asyncio.Lock()

# 429 重试配置
_MAX_RETRIES: int = 3
_RETRY_BASE_DELAY: float = 5.0  # 首次重试等 5s，之后指数增长


async def _rate_limit_wait() -> None:
    """确保两次 API 调用之间至少间隔 _MIN_REQUEST_INTERVAL 秒。"""
    global _last_request_time
    async with _rate_lock:
        now = time.monotonic()
        elapsed = now - _last_request_time
        if elapsed < _MIN_REQUEST_INTERVAL:
            wait = _MIN_REQUEST_INTERVAL - elapsed
            logger.debug(f"[citoapi] 速率限制: 等待 {wait:.1f}s")
            await asyncio.sleep(wait)
        _last_request_time = time.monotonic()


# ── 通用请求 ──

async def _request(endpoint: str, params: dict | None = None) -> dict[str, Any]:
    url = f"{_BASE_URL}{endpoint}" if not endpoint.startswith("http") else endpoint

    for attempt in range(_MAX_RETRIES + 1):
        await _rate_limit_wait()
        try:
            client = await _get_client()
            resp = await client.get(url, params=params or {})
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            detail = e.response.text[:300]

            # 429 → 指数退避重试
            if status == 429 and attempt < _MAX_RETRIES:
                delay = _RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    f"[citoapi] 429 请求频率过高，第 {attempt + 1}/{_MAX_RETRIES} 次重试，"
                    f"等待 {delay:.0f}s..."
                )
                await asyncio.sleep(delay)
                continue

            error_msg = f"HTTP {status}"
            if status == 403:
                error_msg += " — API Key 无效或已过期"
            elif status == 401:
                error_msg += " — API Key 未授权"
            elif status == 429:
                error_msg += " — 请求频率过高，重试已耗尽"
            elif status >= 500:
                error_msg += " — citoapi 服务器错误，请稍后重试"
            else:
                error_msg += f" — {detail}"
            logger.error(f"[citoapi] {error_msg}\n{traceback.format_exc()}")
            return {"_error": error_msg, "_status": status}
        except Exception as exc:
            if attempt < _MAX_RETRIES:
                delay = _RETRY_BASE_DELAY * (2 ** attempt)
                logger.debug(f"[citoapi] 网络异常重试 {attempt + 1}/{_MAX_RETRIES}: {exc}")
                await asyncio.sleep(delay)
                continue
            exc_type = type(exc).__name__
            error_msg = f"网络请求异常 [{exc_type}]: {exc}"
            logger.error(f"[citoapi] {error_msg}\n{traceback.format_exc()}")
            return {"_error": error_msg, "_status": 0}

    return {"_error": "请求失败: 重试次数已耗尽", "_status": 429}


async def _api_call(endpoint: str, params: dict | None = None) -> JsonResult:
    """调用 citoapi 端点并自动处理错误。

    所有简单端点统一使用此函数，确保 _error 检查不被遗漏。
    如果 API 返回顶层列表，自动包装为 {"data": [...]} 以兼容下游 dict 接口。
    """
    data = await _request(endpoint, params)
    if "_error" in data:
        return Failure(error=data["_error"])
    # 如果 API 返回列表，包装为 {"data": [...]} 方便上游统一处理
    if isinstance(data, list):
        return Success(value={"data": data})
    return Success(value=data)


# ═══════════════════════════════════════════════════
#  赛程 — GET /lol/leagues/{slug}/schedule
# ═══════════════════════════════════════════════════

async def fetch_schedule(league: str = "lck") -> ScheduleResult:
    slug = (league or "").strip().lower()
    cito = _cito_slug(slug)
    if not cito:
        return Failure(error=f"不支持的赛区: {slug}，可用: {supported_leagues()}")

    data = await _request(f"/lol/leagues/{cito}/schedule")
    if "_error" in data:
        return Failure(error=data["_error"])

    events = _extract_events(data)
    matches: list[LeagueMatch] = []
    for ev in events:
        m = _parse_match_event(ev, slug)
        if m:
            matches.append(m)
    return Success(value=matches) if matches else Success(value=[])


def _extract_events(data: dict) -> list[dict]:
    if isinstance(data, list):
        return data
    if "events" in data:
        return data.get("events", [])
    sched = data.get("schedule", {})
    if isinstance(sched, dict) and "events" in sched:
        return sched["events"]
    inner = data.get("data", {})
    if isinstance(inner, dict):
        s2 = inner.get("schedule", {})
        if isinstance(s2, dict) and "events" in s2:
            return s2["events"]
        if "events" in inner:
            return inner["events"]
    if "matches" in data:
        return data["matches"]
    return []


# ═══════════════════════════════════════════════════
#  类别 1 — Leagues（联赛信息）
# ═══════════════════════════════════════════════════

async def fetch_all_leagues() -> JsonResult:
    """获取所有联赛列表 GET /lol/leagues"""
    return await _api_call("/lol/leagues")


async def fetch_league_details(slug: str) -> JsonResult:
    """获取联赛详情 GET /lol/leagues/{slug}"""
    return await _api_call(f"/lol/leagues/{slug}")


# ═══════════════════════════════════════════════════
#  类别 2 — Schedule（赛程）
# ═══════════════════════════════════════════════════

async def fetch_schedule_by_date(league: str, date: str) -> JsonResult:
    """按日期获取赛程 GET /lol/leagues/{slug}/schedule?date=2025-01-15"""
    slug = _resolve_slug(league)
    return await _api_call(f"/lol/leagues/{slug}/schedule", {"date": date})


async def fetch_upcoming_matches(league: str, limit: int = 10) -> JsonResult:
    """获取即将到来的比赛 GET /lol/schedule/upcoming"""
    slug = _resolve_slug(league)
    return await _api_call("/lol/schedule/upcoming", {"league": slug, "limit": str(limit)})


async def fetch_completed_matches(league: str, limit: int = 10) -> JsonResult:
    """获取已完成的比赛 GET /lol/schedule/completed"""
    slug = _resolve_slug(league)
    return await _api_call("/lol/schedule/completed", {"league": slug, "limit": str(limit)})


async def fetch_today_schedule(league: str = "") -> JsonResult:
    """获取今日赛程 GET /lol/schedule/today"""
    params: dict[str, str] = {}
    if league:
        params["league"] = _resolve_slug(league)
    return await _api_call("/lol/schedule/today", params)


async def fetch_week_schedule(league: str = "") -> JsonResult:
    """获取本周赛程 GET /lol/schedule/week"""
    params: dict[str, str] = {}
    if league:
        params["league"] = _resolve_slug(league)
    return await _api_call("/lol/schedule/week", params)


# ═══════════════════════════════════════════════════
#  类别 3 — Live（实时比赛）
# ═══════════════════════════════════════════════════

async def fetch_live_window(game_id: str) -> JsonResult:
    """获取实时比赛窗口数据 GET /lol/live/games/{gameId}/window"""
    return await _api_call(f"/lol/live/games/{game_id}/window")


async def fetch_live_stats(game_id: str) -> JsonResult:
    """获取实时比赛统计数据 GET /lol/live/games/{gameId}/stats"""
    return await _api_call(f"/lol/live/games/{game_id}/stats")


async def fetch_live_timeline(game_id: str) -> JsonResult:
    """获取实时比赛时间线 GET /lol/live/games/{gameId}/timeline"""
    return await _api_call(f"/lol/live/games/{game_id}/timeline")


async def fetch_live_events(game_id: str) -> JsonResult:
    """获取实时比赛事件 GET /lol/live/games/{gameId}/events"""
    return await _api_call(f"/lol/live/games/{game_id}/events")


# ═══════════════════════════════════════════════════
#  类别 4 — Matches（比赛详情）
# ═══════════════════════════════════════════════════

async def fetch_match_info(match_id: str) -> JsonResult:
    """获取比赛基本信息 GET /lol/matches/{matchId}"""
    return await _api_call(f"/lol/matches/{match_id}")


async def fetch_match_timeline(match_id: str) -> JsonResult:
    """获取比赛时间线 GET /lol/matches/{matchId}/timeline"""
    return await _api_call(f"/lol/matches/{match_id}/timeline")


async def fetch_match_players(match_id: str) -> JsonResult:
    """获取比赛选手信息 GET /lol/matches/{matchId}/players"""
    return await _api_call(f"/lol/matches/{match_id}/players")


async def fetch_match_builds(match_id: str) -> JsonResult:
    """获取比赛出装信息 GET /lol/matches/{matchId}/builds"""
    return await _api_call(f"/lol/matches/{match_id}/builds")


async def fetch_match_stats(match_id: str) -> JsonResult:
    """获取比赛统计数据 GET /lol/matches/{matchId}/stats"""
    return await _api_call(f"/lol/matches/{match_id}/stats")


async def fetch_match_leaderboards(match_id: str) -> JsonResult:
    """获取比赛排行榜 GET /lol/matches/{matchId}/leaderboards"""
    return await _api_call(f"/lol/matches/{match_id}/leaderboards")


# ═══════════════════════════════════════════════════
#  类别 5 — Games（单局详情）
# ═══════════════════════════════════════════════════

async def fetch_game_info(game_id: str) -> JsonResult:
    """获取单局比赛信息 GET /lol/games/{gameId}"""
    return await _api_call(f"/lol/games/{game_id}")


async def fetch_game_timeline(game_id: str) -> JsonResult:
    """获取单局时间线 GET /lol/games/{gameId}/timeline"""
    return await _api_call(f"/lol/games/{game_id}/timeline")


async def fetch_game_stats(game_id: str) -> JsonResult:
    """获取单局统计数据 GET /lol/games/{gameId}/stats"""
    return await _api_call(f"/lol/games/{game_id}/stats")


async def fetch_game_events(game_id: str) -> JsonResult:
    """获取单局事件 GET /lol/games/{gameId}/events"""
    return await _api_call(f"/lol/games/{game_id}/events")


async def fetch_game_builds(game_id: str) -> JsonResult:
    """获取单局出装 GET /lol/games/{gameId}/builds"""
    return await _api_call(f"/lol/games/{game_id}/builds")


async def fetch_game_runes(game_id: str) -> JsonResult:
    """获取单局符文 GET /lol/games/{gameId}/runes"""
    return await _api_call(f"/lol/games/{game_id}/runes")


async def fetch_game_drafts(game_id: str) -> JsonResult:
    """获取单局 BP 详情 GET /lol/games/{gameId}/drafts"""
    return await _api_call(f"/lol/games/{game_id}/drafts")


async def fetch_game_leaderboards(game_id: str) -> JsonResult:
    """获取单局排行榜 GET /lol/games/{gameId}/leaderboards"""
    return await _api_call(f"/lol/games/{game_id}/leaderboards")


# ═══════════════════════════════════════════════════
#  类别 6 — Teams（战队）
# ═══════════════════════════════════════════════════

async def fetch_all_teams(league: str = "") -> JsonResult:
    """获取所有战队 GET /lol/teams"""
    params: dict[str, str] = {}
    if league:
        params["league"] = _resolve_slug(league)
    return await _api_call("/lol/teams", params)


async def fetch_team(team_id: str) -> JsonResult:
    """获取战队信息 GET /lol/teams/{teamId}"""
    return await _api_call(f"/lol/teams/{team_id}")


async def fetch_team_roster(team_id: str) -> JsonResult:
    """获取战队阵容 GET /lol/teams/{teamId}/roster"""
    return await _api_call(f"/lol/teams/{team_id}/roster")


async def fetch_team_matches(team_id: str, limit: int = 10) -> JsonResult:
    """获取战队比赛记录 GET /lol/teams/{teamId}/matches"""
    return await _api_call(f"/lol/teams/{team_id}/matches", {"limit": str(limit)})


async def fetch_team_stats(team_id: str, season: str = "current") -> JsonResult:
    """获取战队统计数据 GET /lol/teams/{teamId}/stats"""
    return await _api_call(f"/lol/teams/{team_id}/stats", {"season": season})


async def fetch_team_h2h(team_a: str, team_b: str) -> JsonResult:
    """获取战队交手记录 GET /lol/teams/{teamA}/h2h/{teamB}"""
    return await _api_call(f"/lol/teams/{team_a}/h2h/{team_b}")


async def fetch_team_vs(team_id: str) -> JsonResult:
    """获取战队对阵统计 GET /lol/teams/{teamId}/vs"""
    return await _api_call(f"/lol/teams/{team_id}/vs")


async def fetch_team_leaderboards(team_id: str) -> JsonResult:
    """获取战队排行榜数据 GET /lol/teams/{teamId}/leaderboards"""
    return await _api_call(f"/lol/teams/{team_id}/leaderboards")


async def fetch_team_champions(team_id: str) -> JsonResult:
    """获取战队英雄使用统计 GET /lol/teams/{teamId}/champions"""
    return await _api_call(f"/lol/teams/{team_id}/champions")


# ═══════════════════════════════════════════════════
#  类别 7 — Players（选手）
# ═══════════════════════════════════════════════════

async def fetch_all_players(league: str = "", team: str = "") -> JsonResult:
    """获取所有选手 GET /lol/players"""
    params: dict[str, str] = {}
    if league:
        params["league"] = _resolve_slug(league)
    if team:
        params["team"] = team
    return await _api_call("/lol/players", params)


async def fetch_player(player_id: str) -> JsonResult:
    """获取选手信息 GET /lol/players/{playerId}"""
    return await _api_call(f"/lol/players/{player_id}")


async def fetch_player_stats(player_id: str, season: str = "current") -> JsonResult:
    """获取选手统计数据 GET /lol/players/{playerId}/stats"""
    return await _api_call(f"/lol/players/{player_id}/stats", {"season": season})


async def fetch_player_career(player_id: str) -> JsonResult:
    """获取选手生涯数据 GET /lol/players/{playerId}/career"""
    return await _api_call(f"/lol/players/{player_id}/career")


async def fetch_player_champions(player_id: str) -> JsonResult:
    """获取选手英雄使用统计 GET /lol/players/{playerId}/champions"""
    return await _api_call(f"/lol/players/{player_id}/champions")


async def fetch_player_matches(player_id: str, limit: int = 10) -> JsonResult:
    """获取选手比赛记录 GET /lol/players/{playerId}/matches"""
    return await _api_call(f"/lol/players/{player_id}/matches", {"limit": str(limit)})


async def fetch_player_leaderboards(player_id: str) -> JsonResult:
    """获取选手排行榜 GET /lol/players/{playerId}/leaderboards"""
    return await _api_call(f"/lol/players/{player_id}/leaderboards")


# ═══════════════════════════════════════════════════
#  类别 8 — Tournaments（锦标赛/赛事）
# ═══════════════════════════════════════════════════

async def fetch_all_tournaments(league: str = "") -> JsonResult:
    """获取所有锦标赛 GET /lol/tournaments"""
    params: dict[str, str] = {}
    if league:
        params["league"] = _resolve_slug(league)
    return await _api_call("/lol/tournaments", params)


async def fetch_tournament(tournament_id: str) -> JsonResult:
    """获取锦标赛信息 GET /lol/tournaments/{tournamentId}"""
    slug = _resolve_tournament_slug(tournament_id)
    return await _api_call(f"/lol/tournaments/{slug}")


async def fetch_tournament_standings(tournament_id: str) -> JsonResult:
    """获取锦标赛积分榜 GET /lol/tournaments/{tournamentId}/standings"""
    slug = _resolve_tournament_slug(tournament_id)
    return await _api_call(f"/lol/tournaments/{slug}/standings")


async def fetch_tournament_bracket(tournament_id: str) -> JsonResult:
    """获取锦标赛淘汰赛对阵 GET /lol/tournaments/{tournamentId}/bracket"""
    slug = _resolve_tournament_slug(tournament_id)
    return await _api_call(f"/lol/tournaments/{slug}/bracket")


async def fetch_tournament_matches(tournament_id: str, limit: int = 20) -> JsonResult:
    """获取锦标赛比赛列表 GET /lol/tournaments/{tournamentId}/matches"""
    slug = _resolve_tournament_slug(tournament_id)
    return await _api_call(f"/lol/tournaments/{slug}/matches", {"limit": str(limit)})


async def fetch_tournament_mvp(tournament_id: str) -> JsonResult:
    """获取锦标赛 MVP GET /lol/tournaments/{tournamentId}/mvp"""
    slug = _resolve_tournament_slug(tournament_id)
    return await _api_call(f"/lol/tournaments/{slug}/mvp")


async def fetch_tournament_teams(tournament_id: str) -> JsonResult:
    """获取锦标赛参赛队伍 GET /lol/tournaments/{tournamentId}/teams"""
    slug = _resolve_tournament_slug(tournament_id)
    return await _api_call(f"/lol/tournaments/{slug}/teams")


async def fetch_tournament_stats(tournament_id: str) -> JsonResult:
    """获取锦标赛统计数据 GET /lol/tournaments/{tournamentId}/stats"""
    slug = _resolve_tournament_slug(tournament_id)
    return await _api_call(f"/lol/tournaments/{slug}/stats")


async def fetch_tournament_leaderboards(tournament_id: str) -> JsonResult:
    """获取锦标赛排行榜 GET /lol/tournaments/{tournamentId}/leaderboards"""
    slug = _resolve_tournament_slug(tournament_id)
    return await _api_call(f"/lol/tournaments/{slug}/leaderboards")


# ═══════════════════════════════════════════════════
#  类别 9 — Standings（积分榜/排名）
# ═══════════════════════════════════════════════════

async def fetch_league_group_standings(league: str, group: str = "") -> JsonResult:
    """获取联赛分组积分榜 GET /lol/leagues/{slug}/standings?group=A"""
    slug = _resolve_slug(league)
    params: dict[str, str] = {}
    if group:
        params["group"] = group
    return await _api_call(f"/lol/leagues/{slug}/standings", params)


async def fetch_detailed_standings(league: str, season: str = "current") -> JsonResult:
    """获取详细积分榜 GET /lol/standings?league=xxx&season=xxx"""
    slug = _resolve_slug(league)
    return await _api_call("/lol/standings", {"league": slug, "season": season})


# ═══════════════════════════════════════════════════
#  类别 10 — Champions（英雄数据）
# ═══════════════════════════════════════════════════

async def fetch_champion_stats(league: str = "", season: str = "current") -> JsonResult:
    """获取英雄统计 GET /lol/champions/stats"""
    params: dict[str, str] = {"season": season}
    if league:
        params["league"] = _resolve_slug(league)
    return await _api_call("/lol/champions/stats", params)


async def fetch_champion_presence(league: str = "", season: str = "current") -> JsonResult:
    """获取英雄 Pick/Ban 率 GET /lol/champions/presence"""
    params: dict[str, str] = {"season": season}
    if league:
        params["league"] = _resolve_slug(league)
    return await _api_call("/lol/champions/presence", params)


async def fetch_champion_matchups(champion: str, league: str = "") -> JsonResult:
    """获取英雄对阵数据 GET /lol/champions/{name}/matchups"""
    params: dict[str, str] = {}
    if league:
        params["league"] = _resolve_slug(league)
    return await _api_call(f"/lol/champions/{champion}/matchups", params)


async def fetch_champion_details(champion: str) -> JsonResult:
    """获取英雄详细信息 GET /lol/champions/{name}"""
    return await _api_call(f"/lol/champions/{champion}")


# ═══════════════════════════════════════════════════
#  类别 11 — Rankings（排行榜）
# ═══════════════════════════════════════════════════

async def fetch_global_power_rankings() -> JsonResult:
    """获取全球战力排名 GET /lol/rankings/gpr"""
    return await _api_call("/lol/rankings/gpr")


async def fetch_player_rankings(metric: str = "kda", limit: int = 20) -> JsonResult:
    """获取选手排名 GET /lol/rankings/players?metric=kda|kills|deaths|assists|cs"""
    return await _api_call("/lol/rankings/players", {"metric": metric, "limit": str(limit)})


async def fetch_team_rankings(metric: str = "wins", limit: int = 20) -> JsonResult:
    """获取战队排名 GET /lol/rankings/teams?metric=wins|losses|winrate"""
    return await _api_call("/lol/rankings/teams", {"metric": metric, "limit": str(limit)})


# ═══════════════════════════════════════════════════
#  类别 12 — History（历史数据）
# ═══════════════════════════════════════════════════

async def fetch_worlds_history() -> JsonResult:
    """获取世界赛历史 GET /lol/history/worlds"""
    return await _api_call("/lol/history/worlds")


async def fetch_msi_history() -> JsonResult:
    """获取 MSI 历史 GET /lol/history/msi"""
    return await _api_call("/lol/history/msi")


async def fetch_regional_history(league: str) -> JsonResult:
    """获取赛区历史 GET /lol/history/regional/{slug}"""
    slug = _resolve_slug(league)
    return await _api_call(f"/lol/history/regional/{slug}")


# ═══════════════════════════════════════════════════
#  类别 13 — Transfers（转会）
# ═══════════════════════════════════════════════════

async def fetch_transfers(league: str = "", season: str = "current") -> JsonResult:
    """获取转会信息 GET /lol/transfers"""
    params: dict[str, str] = {"season": season}
    if league:
        params["league"] = _resolve_slug(league)
    return await _api_call("/lol/transfers", params)


async def fetch_free_agents() -> JsonResult:
    """获取自由选手 GET /lol/transfers/free-agents"""
    return await _api_call("/lol/transfers/free-agents")


# ═══════════════════════════════════════════════════
#  类别 14 — Leaderboards（数据排行）
# ═══════════════════════════════════════════════════

async def fetch_leaderboards_kda(league: str = "", season: str = "current") -> JsonResult:
    """KDA 排行榜 GET /lol/leaderboards/kda"""
    params: dict[str, str] = {"season": season}
    if league:
        params["league"] = _resolve_slug(league)
    return await _api_call("/lol/leaderboards/kda", params)


async def fetch_leaderboards_kills(league: str = "", season: str = "current") -> JsonResult:
    """击杀榜 GET /lol/leaderboards/kills"""
    params: dict[str, str] = {"season": season}
    if league:
        params["league"] = _resolve_slug(league)
    return await _api_call("/lol/leaderboards/kills", params)


async def fetch_leaderboards_deaths(league: str = "", season: str = "current") -> JsonResult:
    """死亡榜 GET /lol/leaderboards/deaths"""
    params: dict[str, str] = {"season": season}
    if league:
        params["league"] = _resolve_slug(league)
    return await _api_call("/lol/leaderboards/deaths", params)


async def fetch_leaderboards_assists(league: str = "", season: str = "current") -> JsonResult:
    """助攻榜 GET /lol/leaderboards/assists"""
    params: dict[str, str] = {"season": season}
    if league:
        params["league"] = _resolve_slug(league)
    return await _api_call("/lol/leaderboards/assists", params)


async def fetch_leaderboards_cs(league: str = "", season: str = "current") -> JsonResult:
    """补刀榜 GET /lol/leaderboards/cs"""
    params: dict[str, str] = {"season": season}
    if league:
        params["league"] = _resolve_slug(league)
    return await _api_call("/lol/leaderboards/cs", params)


async def fetch_leaderboards_gold(league: str = "", season: str = "current") -> JsonResult:
    """经济榜 GET /lol/leaderboards/gold"""
    params: dict[str, str] = {"season": season}
    if league:
        params["league"] = _resolve_slug(league)
    return await _api_call("/lol/leaderboards/gold", params)


async def fetch_leaderboards_vision(league: str = "", season: str = "current") -> JsonResult:
    """视野榜 GET /lol/leaderboards/vision"""
    params: dict[str, str] = {"season": season}
    if league:
        params["league"] = _resolve_slug(league)
    return await _api_call("/lol/leaderboards/vision", params)


async def fetch_leaderboards_damage(league: str = "", season: str = "current") -> JsonResult:
    """伤害榜 GET /lol/leaderboards/damage"""
    params: dict[str, str] = {"season": season}
    if league:
        params["league"] = _resolve_slug(league)
    return await _api_call("/lol/leaderboards/damage", params)


# ═══════════════════════════════════════════════════
#  类别 15 — Search（搜索）
# ═══════════════════════════════════════════════════

async def search_teams(query: str) -> JsonResult:
    """搜索战队 GET /lol/search/teams?q=xxx"""
    return await _api_call("/lol/search/teams", {"q": query})


async def search_players(query: str) -> JsonResult:
    """搜索选手 GET /lol/search/players?q=xxx"""
    return await _api_call("/lol/search/players", {"q": query})


async def search_tournaments(query: str) -> JsonResult:
    """搜索锦标赛 GET /lol/search/tournaments?q=xxx"""
    return await _api_call("/lol/search/tournaments", {"q": query})


async def search_matches(league: str = "", query: str = "") -> JsonResult:
    """搜索比赛 GET /lol/search/matches"""
    params: dict[str, str] = {}
    if league:
        params["league"] = _resolve_slug(league)
    if query:
        params["q"] = query
    return await _api_call("/lol/search/matches", params)


# ═══════════════════════════════════════════════════
#  类别 16 — Trending（热门趋势）
# ═══════════════════════════════════════════════════

async def fetch_trending() -> JsonResult:
    """获取热门趋势 GET /lol/trending"""
    return await _api_call("/lol/trending")


async def fetch_trending_players() -> JsonResult:
    """获取热门选手 GET /lol/trending/players"""
    return await _api_call("/lol/trending/players")


async def fetch_trending_teams() -> JsonResult:
    """获取热门战队 GET /lol/trending/teams"""
    return await _api_call("/lol/trending/teams")


async def fetch_trending_champions() -> JsonResult:
    """获取热门英雄 GET /lol/trending/champions"""
    return await _api_call("/lol/trending/champions")


# ═══════════════════════════════════════════════════
#  类别 17 — Static Data（静态数据）
# ═══════════════════════════════════════════════════

async def fetch_static_champions() -> JsonResult:
    """获取所有英雄数据 GET /lol/static/champions"""
    return await _api_call("/lol/static/champions")


async def fetch_static_items() -> JsonResult:
    """获取所有装备数据 GET /lol/static/items"""
    return await _api_call("/lol/static/items")


async def fetch_static_runes() -> JsonResult:
    """获取所有符文数据 GET /lol/static/runes"""
    return await _api_call("/lol/static/runes")


async def fetch_static_summoner_spells() -> JsonResult:
    """获取召唤师技能 GET /lol/static/summonerspells"""
    return await _api_call("/lol/static/summonerspells")


async def fetch_static_patches() -> JsonResult:
    """获取版本列表 GET /lol/static/patches"""
    return await _api_call("/lol/static/patches")


async def fetch_static_patch_notes(patch: str) -> JsonResult:
    """获取版本更新说明 GET /lol/static/patches/{version}"""
    return await _api_call(f"/lol/static/patches/{patch}")


# ═══════════════════════════════════════════════════
#  类别 18 — Regions（赛区）
# ═══════════════════════════════════════════════════

async def fetch_regions() -> JsonResult:
    """获取所有赛区 GET /lol/regions"""
    return await _api_call("/lol/regions")


# ═══════════════════════════════════════════════════
#  类别 19 — Roles（位置）
# ═══════════════════════════════════════════════════

async def fetch_roles() -> JsonResult:
    """获取所有位置列表 GET /lol/roles"""
    return await _api_call("/lol/roles")


# ═══════════════════════════════════════════════════
#  类别 20 — Records（记录/里程碑）
# ═══════════════════════════════════════════════════

async def fetch_records(league: str = "") -> JsonResult:
    """获取赛事记录 GET /lol/records"""
    params: dict[str, str] = {}
    if league:
        params["league"] = _resolve_slug(league)
    return await _api_call("/lol/records", params)


async def fetch_milestones(league: str = "") -> JsonResult:
    """获取里程碑 GET /lol/records/milestones"""
    params: dict[str, str] = {}
    if league:
        params["league"] = _resolve_slug(league)
    return await _api_call("/lol/records/milestones", params)


# ═══════════════════════════════════════════════════
#  类别 21 — Awards（奖项）
# ═══════════════════════════════════════════════════

async def fetch_awards(league: str = "") -> JsonResult:
    """获取奖项列表 GET /lol/awards"""
    params: dict[str, str] = {}
    if league:
        params["league"] = _resolve_slug(league)
    return await _api_call("/lol/awards", params)


async def fetch_mvp_awards(league: str = "", season: str = "current") -> JsonResult:
    """获取 MVP 奖项 GET /lol/awards/mvp"""
    params: dict[str, str] = {"season": season}
    if league:
        params["league"] = _resolve_slug(league)
    return await _api_call("/lol/awards/mvp", params)


async def fetch_allstar_info() -> JsonResult:
    """获取全明星赛信息 GET /lol/allstar"""
    return await _api_call("/lol/allstar")


async def fetch_playoffs_info() -> JsonResult:
    """获取季后赛信息 GET /lol/playoffs"""
    return await _api_call("/lol/playoffs")


# ═══════════════════════════════════════════════════
#  聚合查询（跨端点组合）
# ═══════════════════════════════════════════════════

async def fetch_team_full_profile(team_id: str) -> JsonResult:
    """聚合获取战队完整画像（信息+阵容+统计+近期比赛）"""
    results: dict[str, Any] = {}
    endpoints = {
        "info": f"/lol/teams/{team_id}",
        "roster": f"/lol/teams/{team_id}/roster",
        "stats": f"/lol/teams/{team_id}/stats",
        "matches": f"/lol/teams/{team_id}/matches",
    }
    errors: list[str] = []
    for key, path in endpoints.items():
        data = await _request(path)
        if "_error" in data:
            errors.append(data["_error"])
            results[key] = None
        else:
            results[key] = data
    if errors and all(v is None for v in results.values()):
        return Failure(error="; ".join(errors))
    return Success(value=results)


async def fetch_player_full_profile(player_id: str) -> JsonResult:
    """聚合获取选手完整画像（信息+统计+生涯+英雄池）"""
    results: dict[str, Any] = {}
    endpoints = {
        "info": f"/lol/players/{player_id}",
        "stats": f"/lol/players/{player_id}/stats",
        "career": f"/lol/players/{player_id}/career",
        "champions": f"/lol/players/{player_id}/champions",
    }
    errors: list[str] = []
    for key, path in endpoints.items():
        data = await _request(path)
        if "_error" in data:
            errors.append(data["_error"])
            results[key] = None
        else:
            results[key] = data
    if errors and all(v is None for v in results.values()):
        return Failure(error="; ".join(errors))
    return Success(value=results)


async def fetch_tournament_full(tournament_id: str) -> JsonResult:
    """聚合获取锦标赛全貌（信息+积分榜+对阵+MVP+排行榜）"""
    slug = _resolve_tournament_slug(tournament_id)
    results: dict[str, Any] = {}
    endpoints = {
        "info": f"/lol/tournaments/{slug}",
        "standings": f"/lol/tournaments/{slug}/standings",
        "bracket": f"/lol/tournaments/{slug}/bracket",
        "mvp": f"/lol/tournaments/{slug}/mvp",
        "leaderboards": f"/lol/tournaments/{slug}/leaderboards",
    }
    errors: list[str] = []
    for key, path in endpoints.items():
        data = await _request(path)
        if "_error" in data:
            errors.append(data["_error"])
            results[key] = None
        else:
            results[key] = data
    if errors and all(v is None for v in results.values()):
        return Failure(error="; ".join(errors))
    return Success(value=results)


# ═══════════════════════════════════════════════════
#  辅助函数
# ═══════════════════════════════════════════════════

def _resolve_slug(user_league: str) -> str:
    """将用户侧 league 转换为 citoapi 的 slug，未知则原样返回。"""
    from ..utils import normalize_league
    normalized = normalize_league(user_league)
    if not normalized:
        return user_league
    return _LEAGUE_SLUGS.get(normalized, user_league)


def _parse_match_event(ev: dict, league_slug: str) -> LeagueMatch | None:
    """解析赛程事件为 LeagueMatch。"""
    # 过滤非 match 类型事件
    ev_type = ev.get("type", ev.get("eventType", ev.get("state", "")))
    if ev_type and ev_type not in ("match", "in_progress", "completed", "unstarted", ""):
        return None

    m = ev.get("match", ev)
    teams_raw = m.get("teams", ev.get("teams", []))
    teams = [
        t.get("name", t.get("code", t.get("team", {}).get("name", "?")))
        for t in teams_raw
    ] if isinstance(teams_raw, list) else []

    start_time = ev.get("startTime", m.get("startTime", ev.get("start_time", "")))
    dt = _parse_iso(start_time) if start_time else ("", "")

    strategy = m.get("strategy", ev.get("strategy", {}))
    bo = strategy.get("count", ev.get("bo", 0)) if strategy else 0

    status = m.get("state", m.get("status", ev.get("state", ev.get("status", ""))))
    arena = (
        ev.get("blockName", "")
        or ev.get("arena", "")
        or (ev.get("league", {}) or {}).get("name", "")
    )

    # round: 优先使用 matchNumber / number / round，fallback 到 match id
    round_val = (
        str(m.get("number", m.get("matchNumber", m.get("round", ""))))
        or str(ev.get("number", ev.get("matchNumber", ev.get("round", ""))))
        or str(m.get("id", ev.get("id", "")))
    )

    # match_id: API 查找所需的真实 match id
    match_id = str(
        m.get("id", "")
        or ev.get("matchId", "")
        or ev.get("id", "")
    )

    return LeagueMatch(
        league=league_slug.upper(),
        stage=strategy.get("type", ev.get("stage", "regular")) if strategy else "regular",
        round=round_val,
        match_id=match_id,
        match_name=" vs ".join(teams) if teams else ev.get("name", ev.get("match_name", "")),
        bo_type=f"BO{bo}" if bo else "",
        start_date=dt[0],
        start_time=dt[1],
        status=status,
        arena=arena,
        teams=teams,
    )


# ═══════════════════════════════════════════════════
#  实时比赛 — GET /lol/live
# ═══════════════════════════════════════════════════

async def fetch_live_matches(league: str | None = None) -> LiveResult:
    data = await _request("/lol/live")
    if "_error" in data:
        return Failure(error=data["_error"])

    events = _extract_events(data)
    live_matches: list[LiveMatch] = []

    for ev in events:
        m = ev.get("match", ev)
        league_slug = ev.get("league", ev.get("leagueId", ""))
        if isinstance(league_slug, dict):
            league_slug = league_slug.get("slug", league_slug.get("id", ""))

        if league:
            target_cito = _cito_slug(league.strip().lower())
            if target_cito and league_slug:
                ls_lower = str(league_slug).lower()
                # league_slug 可能是 "lck" 或 "lol-lck"，统一比较
                target_short = target_cito.replace("lol-", "")
                if ls_lower not in (target_short, target_cito):
                    continue

        teams_raw = m.get("teams", ev.get("teams", []))
        teams = [
            t.get("name", t.get("code", t.get("team", {}).get("name", "?")))
            for t in teams_raw
        ] if isinstance(teams_raw, list) else []

        strategy = m.get("strategy", ev.get("strategy", {}))
        bo = strategy.get("count", ev.get("bo", 0)) if strategy else 0

        games: list[LiveGameFrame] = []
        for g in m.get("games", ev.get("games", [])):
            gid = g.get("id", g.get("gameId", ""))
            state = g.get("state", g.get("status", ""))
            gteams = g.get("teams", [])
            blue = _pick_side(gteams, "blue")
            red = _pick_side(gteams, "red")

            games.append(LiveGameFrame(
                game_id=str(gid),
                game_no=g.get("number", g.get("gameNo", 0)),
                state=state,
                blue_team=blue.get("name", blue.get("code", "蓝方")),
                red_team=red.get("name", red.get("code", "红方")),
                winner=(
                    "blue" if blue.get("result", {}).get("outcome") == "win"
                    else "red" if red.get("result", {}).get("outcome") == "win"
                    else ""
                ),
            ))

        blue_wins = sum(1 for g in games if g.winner == "blue")
        red_wins = sum(1 for g in games if g.winner == "red")

        live_matches.append(LiveMatch(
            match_id=str(m.get("id", ev.get("id", ""))),
            league=str(league_slug).lower() if league_slug else "",
            league_name=str(league_slug) if league_slug else "",
            tournament_id=str(ev.get("tournamentId", ev.get("tournament", {}).get("id", ""))
                              if isinstance(ev.get("tournament"), dict) else ""),
            match_name=" vs ".join(teams) if teams else ev.get("name", ""),
            teams=teams,
            score=f"{blue_wins}:{red_wins}",
            bo_type=f"BO{bo}" if bo else "",
            status=m.get("state", m.get("status", "")),
            games=games,
        ))

    return Success(value=live_matches)


# ═══════════════════════════════════════════════════
#  实时帧 — GET /lol/live/games/{gameId}/window
# ═══════════════════════════════════════════════════

async def fetch_live_frame(game_id: str, since: int = 0) -> LiveGameFrame | None:
    endpoint = f"/lol/live/games/{game_id}/window"
    params: dict[str, Any] = {}
    if since > 0:
        params["startingTime"] = str(since)

    try:
        data = await _request(endpoint, params=params)
        if "_error" in data:
            return None

        frames = data.get("frames", []) if isinstance(data, dict) else []
        if not frames and isinstance(data, list):
            frames = data[-1:]

        latest = frames[-1] if frames else data
        if not latest:
            return None

        game_state = latest.get("gameState", data.get("gameState", latest.get("state", "")))
        blue = latest.get("blueTeam", data.get("blueTeam", {}))
        red = latest.get("redTeam", data.get("redTeam", {}))

        return LiveGameFrame(
            game_id=game_id,
            game_no=0,
            state=game_state,
            blue_team=blue.get("name", ""),
            red_team=red.get("name", ""),
            blue_kills=blue.get("totalKills", blue.get("kills", 0)),
            red_kills=red.get("totalKills", red.get("kills", 0)),
            blue_gold=blue.get("totalGold", blue.get("gold", 0)),
            red_gold=red.get("totalGold", red.get("gold", 0)),
            blue_towers=blue.get("towers", 0),
            red_towers=red.get("towers", 0),
            blue_barons=blue.get("barons", 0),
            red_barons=red.get("barons", 0),
            blue_drakes=blue.get("drakes", blue.get("dragons", 0)),
            red_drakes=red.get("drakes", red.get("dragons", 0)),
            blue_inhibitors=blue.get("inhibitors", 0),
            red_inhibitors=red.get("inhibitors", 0),
            game_time=latest.get("gameTime", data.get("gameTime", "")),
            winner=data.get("winner", ""),
        )
    except Exception as e:
        logger.debug(f"[citoapi] Frame error for {game_id}: {e}")
        return None


async def fetch_live_match_details(live_match: LiveMatch) -> LiveMatch:
    updated_games: list[LiveGameFrame] = []
    for game in live_match.games:
        if game.state in ("in_progress", "in-progress", "live") and game.game_id:
            frame = await fetch_live_frame(game.game_id)
            if frame:
                frame.game_no = game.game_no
                updated_games.append(frame)
            else:
                updated_games.append(game)
        else:
            updated_games.append(game)
    live_match.games = updated_games
    return live_match


# ═══════════════════════════════════════════════════
#  排名 — GET /lol/leagues/{slug}/standings
# ═══════════════════════════════════════════════════

async def fetch_standings(league: str = "lck") -> StandingsResult:
    slug = (league or "").strip().lower()
    cito = _cito_slug(slug)
    if not cito:
        return Failure(error=f"不支持的赛区: {slug}，可用: {supported_leagues()}")

    data = await _request(f"/lol/leagues/{cito}/standings")
    if "_error" in data:
        return Failure(error=data["_error"])

    standings_list = data.get("standings", data.get("data", {}).get("standings", []))
    if not standings_list and isinstance(data, list):
        standings_list = data

    entries: list[StandingEntry] = []
    for group in (standings_list if isinstance(standings_list, list) else [standings_list]):
        teams_in_group = group.get("teams", group.get("entries", [])) if isinstance(group, dict) else []
        for team in (teams_in_group if isinstance(teams_in_group, list) else [teams_in_group]):
            if not isinstance(team, dict):
                continue
            record = team.get("record", team.get("stats", {}))
            entries.append(StandingEntry(
                rank=team.get("rank", team.get("position", 0)),
                team_name=team.get("name", team.get("code", "?")),
                wins=record.get("wins", record.get("win", 0)),
                losses=record.get("losses", record.get("loss", 0)),
                points=record.get("wins", record.get("points", record.get("win", 0))),
                status=team.get("status", ""),
            ))

    return Success(value=entries)


# ═══════════════════════════════════════════════════
#  比赛详情 (含 BP) — GET /lol/matches/{matchId}
# ═══════════════════════════════════════════════════

async def fetch_match_detail(match_id: str) -> MatchDetail | None:
    if not match_id:
        return None

    data = await _request(f"/lol/matches/{match_id}")
    if "_error" in data:
        logger.warning(f"[citoapi] match detail failed: {data['_error']}")
        return None

    # 尝试多种嵌套路径找到 event/match 数据
    event = data.get("event", data.get("match", data))
    if isinstance(event, list):
        # API 可能返回列表，取第一个
        event = event[0] if event else {}
    if not isinstance(event, dict):
        logger.debug(f"[citoapi] match detail unexpected type: {type(data)}")
        return None

    match_obj = event.get("match", event)
    if isinstance(match_obj, list):
        match_obj = match_obj[0] if match_obj else {}
    if not isinstance(match_obj, dict):
        match_obj = event

    teams_raw = match_obj.get("teams", event.get("teams", []))
    teams = [t.get("name", t.get("code", "?")) for t in teams_raw] if isinstance(teams_raw, list) else []

    games: list[MatchGame] = []
    for g in match_obj.get("games", event.get("games", [])):
        game_teams = g.get("teams", [])
        blue = _pick_side(game_teams, "blue")
        red = _pick_side(game_teams, "red")

        bp_entries: list[BPEntry] = []
        for side_name, side_data in [("蓝方", blue), ("红方", red)]:
            for ban in side_data.get("bans", []):
                bp_entries.append(BPEntry(
                    side=side_name,
                    champion=ban.get("name", ban.get("championId", "")),
                    player="(ban)",
                    result="ban",
                ))
            for pick in side_data.get("picks", []):
                bp_entries.append(BPEntry(
                    side=side_name,
                    champion=pick.get("name", pick.get("championId", "")),
                    player=pick.get("playerId", pick.get("player", "")),
                    result=pick.get("role", pick.get("position", "")),
                ))

        winner = (
            "blue" if blue.get("result", {}).get("outcome") == "win"
            else "red" if red.get("result", {}).get("outcome") == "win"
            else ""
        )
        winner_name = (
            blue.get("name", "") if winner == "blue"
            else red.get("name", "") if winner == "red"
            else ""
        )

        games.append(MatchGame(
            game_no=g.get("number", g.get("gameNo", 0)),
            blue_team=blue.get("name", blue.get("code", "蓝方")),
            red_team=red.get("name", red.get("code", "红方")),
            winner=winner_name,
            duration=_format_duration(g.get("duration", g.get("gameDuration", 0))),
            bp=bp_entries,
        ))

    tournament = event.get("tournament", {})
    league_name = _extract_league_name(event, tournament)

    return MatchDetail(
        league=league_name,
        stage=tournament.get("stage", event.get("stage", "regular")),
        round=str(match_obj.get("id", event.get("id", match_id))),
        match_name=" vs ".join(teams) if teams else event.get("name", ""),
        summary=event.get("description", event.get("summary", "")),
        games=games,
    )


def _extract_league_name(event: dict, tournament: dict) -> str:
    league = tournament.get("league", tournament.get("leagueId", ""))
    if isinstance(league, dict):
        league = league.get("slug", league.get("name", league.get("id", "")))
    if league:
        return _user_slug_from_cito(str(league)) if "lol-" in str(league) else str(league).upper()
    ev_league = event.get("league", event.get("leagueId", ""))
    if isinstance(ev_league, dict):
        ev_league = ev_league.get("slug", ev_league.get("name", ""))
    return str(ev_league).upper() if ev_league else ""


# ═══════════════════════════════════════════════════
#  工具函数
# ═══════════════════════════════════════════════════

def _parse_iso(iso_str: str) -> tuple[str, str]:
    if not iso_str:
        return ("", "")
    try:
        if isinstance(iso_str, (int, float)):
            dt = datetime.fromtimestamp(iso_str)
        elif str(iso_str).isdigit():
            ts = int(iso_str)
            dt = datetime.fromtimestamp(ts / 1000 if ts > 1e12 else ts)
        else:
            dt = datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
        local = dt.astimezone()
        return (local.strftime("%Y-%m-%d"), local.strftime("%H:%M"))
    except Exception:
        return ("", "")


def _pick_side(teams: list[dict], side: str) -> dict:
    for t in teams:
        if not isinstance(t, dict):
            continue
        if t.get("side", t.get("teamSide", "")).lower() == side:
            return t
    idx = 0 if side == "blue" else 1
    return teams[idx] if idx < len(teams) else {}


def _format_duration(seconds: int) -> str:
    if not seconds:
        return ""
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"
