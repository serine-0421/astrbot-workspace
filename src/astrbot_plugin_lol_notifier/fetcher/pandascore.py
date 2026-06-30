"""PandaScore LoL API 抓取器 — 主数据源。

数据来源：PandaScore (https://api.pandascore.co)
Auth: Bearer token (Authorization header)

端点概览：
  比赛:   GET /lol/matches[/running|upcoming|past]
  联赛:   GET /lol/leagues[/{id}]
  系列赛: GET /lol/series[/{id}]
  锦标赛: GET /lol/tournaments[/{id}]
  战队:   GET /lol/teams[/{id}]
  选手:   GET /lol/players[/{id}]
  积分榜: GET /lol/tournaments/{id}/standings
"""

from __future__ import annotations

import asyncio
import time
import traceback
from typing import Any

import httpx

from astrbot.api import logger

from ..models import (
    Failure,
    JsonListResult,
    JsonResult,
    LeagueMatch,
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

_BASE_URL = "https://api.pandascore.co"

_PANDASCORE_TOKEN = "mKtQmqlyBVChC0sQHPQxIaZubebQZvuSqSfxzW7_5MDbzCuyKw8"

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

# ── League slug 映射（用户输入 → pandascore league name/slug） ──
_LEAGUE_MAP: dict[str, str] = {
    "lck": "lck",
    "lpl": "lpl",
    "lec": "lec",
    "lcs": "lcs",
    "lco": "lco",
    "lcl": "lcl",
    "ljl": "ljl",
    "pcs": "pcs",
    "vcs": "vcs",
    "cblol": "cblol",
    "lla": "lla",
    "tcl": "tcl",
    "msi": "msi",
    "worlds": "worlds",
}


def supported_leagues() -> list[str]:
    return sorted(_LEAGUE_MAP.keys())


def _ps_league(user_slug: str) -> str:
    return _LEAGUE_MAP.get(user_slug.strip().lower(), "")


# ── HTTP Client ──

_client: httpx.AsyncClient | None = None


async def close_session() -> None:
    global _client
    if _client:
        await _client.aclose()
        _client = None


async def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=20.0,
            headers={
                "User-Agent": _USER_AGENT,
                "Accept": "application/json",
                "Authorization": f"Bearer {_PANDASCORE_TOKEN}",
            },
        )
    return _client


# ── 速率限制 ──

_MIN_REQUEST_INTERVAL: float = 1.0  # Pandascore free tier: 2 req/s，留安全余量
_last_request_time: float = 0.0
_rate_lock = asyncio.Lock()

_MAX_RETRIES: int = 3
_RETRY_BASE_DELAY: float = 2.0


async def _rate_limit_wait() -> None:
    global _last_request_time
    async with _rate_lock:
        now = time.monotonic()
        elapsed = now - _last_request_time
        if elapsed < _MIN_REQUEST_INTERVAL:
            wait = _MIN_REQUEST_INTERVAL - elapsed
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

            if status == 429 and attempt < _MAX_RETRIES:
                delay = _RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    f"[PandaScore] 429 速率限制，第 {attempt + 1}/{_MAX_RETRIES} 次重试，"
                    f"等待 {delay:.0f}s..."
                )
                await asyncio.sleep(delay)
                continue

            error_msg = f"HTTP {status}"
            if status == 403:
                error_msg += " — API Token 无效或已过期"
            elif status == 401:
                error_msg += " — API Token 未授权"
            elif status == 429:
                error_msg += " — 请求频率过高，重试已耗尽"
            elif status == 404:
                error_msg += " — 资源未找到"
            elif status >= 500:
                error_msg += " — PandaScore 服务器错误，请稍后重试"
            else:
                error_msg += f" — {detail}"
            logger.error(f"[PandaScore] {error_msg}\n{traceback.format_exc()}")
            return {"_error": error_msg, "_status": status}
        except Exception as exc:
            if attempt < _MAX_RETRIES:
                delay = _RETRY_BASE_DELAY * (2 ** attempt)
                logger.debug(f"[PandaScore] 网络异常重试 {attempt + 1}/{_MAX_RETRIES}: {exc}")
                await asyncio.sleep(delay)
                continue
            exc_type = type(exc).__name__
            error_msg = f"网络请求异常 [{exc_type}]: {exc}"
            logger.error(f"[PandaScore] {error_msg}\n{traceback.format_exc()}")
            return {"_error": error_msg, "_status": 0}

    return {"_error": "请求失败: 重试次数已耗尽", "_status": 429}


async def _ps_call(endpoint: str, params: dict | None = None) -> JsonResult:
    """调用 Pandascore 端点并标准化返回值。"""
    data = await _request(endpoint, params)
    if "_error" in data:
        return Failure(error=data["_error"])
    if isinstance(data, list):
        return Success(value={"data": data})
    return Success(value=data)


# ═══════════════════════════════════════════════════
#  数据解析 — Pandascore JSON → 内部 Model
# ═══════════════════════════════════════════════════

def _ps_parse_match(m: dict, league_hint: str = "") -> LeagueMatch:
    """将 Pandascore match 对象转为 LeagueMatch。"""
    opponents = m.get("opponents") or []
    teams: list[str] = []
    for opp in opponents:
        team = opp.get("opponent", {})
        name = team.get("name") or team.get("acronym") or "TBD"
        teams.append(name)

    # 比分
    results = m.get("results") or []
    scores: list[str] = []
    for r in results:
        scores.append(str(r.get("score", 0)))

    # 状态映射
    status_map = {"not_started": "upcoming", "running": "live", "finished": "completed"}
    status = status_map.get(m.get("status", ""), m.get("status", ""))

    # 联赛信息
    league_obj = m.get("league") or {}
    league_name = league_obj.get("name", league_hint) or league_hint

    # 系列赛
    serie_obj = m.get("serie") or {}
    stage = serie_obj.get("name", "") or "Regular Season"

    # 比赛局数
    number_of_games = m.get("number_of_games", 0)
    bo_type = f"BO{number_of_games}" if number_of_games else ""

    # 时间
    scheduled_at = m.get("scheduled_at", "")
    start_date = ""
    start_time = ""
    if scheduled_at:
        try:
            from datetime import datetime, timezone, timedelta
            dt = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
            beijing_tz = timezone(timedelta(hours=8))
            dt_local = dt.astimezone(beijing_tz)
            start_date = dt_local.strftime("%Y-%m-%d")
            start_time = dt_local.strftime("%H:%M")
        except Exception:
            start_date = scheduled_at[:10] if len(scheduled_at) >= 10 else scheduled_at
            start_time = scheduled_at[11:16] if len(scheduled_at) >= 16 else ""

    # 局数据
    games_data = m.get("games") or []
    games: list[MatchGame] = []
    for g in games_data:
        winner_info = g.get("winner") or {}
        winner_id = winner_info.get("id")
        winner_name = ""
        if winner_id is not None:
            for opp in opponents:
                if opp.get("opponent", {}).get("id") == winner_id:
                    winner_name = opp.get("opponent", {}).get("name") or ""
                    break

        length = g.get("length", 0) or 0
        duration = f"{length // 60}:{length % 60:02d}" if length > 0 else ""

        games.append(MatchGame(
            game_no=g.get("position", 0) or 0,
            blue_team=teams[0] if len(teams) > 0 else "",
            red_team=teams[1] if len(teams) > 1 else "",
            winner=winner_name,
            duration=duration,
        ))

    # 总结
    score_str = ":".join(scores) if scores else ""
    summary = f"{' vs '.join(teams)} {score_str}" if teams else ""
    if status == "live":
        summary = f"🔴 {' vs '.join(teams)} {score_str}"

    return LeagueMatch(
        league=league_name,
        stage=stage,
        round=m.get("name", "") or f"Match #{m.get('id', '')}",
        match_id=str(m.get("id", "")),
        match_name=m.get("name", ""),
        bo_type=bo_type,
        start_date=start_date,
        start_time=start_time,
        status=status,
        arena="",
        teams=teams,
        games=games,
        summary=summary,
    )


def _ps_parse_matches(data_list: list[dict], league_hint: str = "") -> list[LeagueMatch]:
    """批量解析 Pandascore match 列表。"""
    return [_ps_parse_match(m, league_hint) for m in data_list]


def _ps_parse_live_match(m: dict, league_hint: str = "") -> LiveMatch:
    """将 Pandascore running match 转为 LiveMatch。"""
    opponents = m.get("opponents") or []
    teams: list[str] = []
    for opp in opponents:
        team = opp.get("opponent", {})
        name = team.get("name") or team.get("acronym") or "TBD"
        teams.append(name)

    results = m.get("results") or []
    scores: list[str] = []
    for r in results:
        scores.append(str(r.get("score", 0)))
    score_str = ":".join(scores) if scores else ""

    league_obj = m.get("league") or {}
    league_name = league_obj.get("name", league_hint) or league_hint

    number_of_games = m.get("number_of_games", 0)
    bo_type = f"BO{number_of_games}" if number_of_games else ""

    status = m.get("status", "running")

    return LiveMatch(
        match_id=str(m.get("id", "")),
        league=league_name.lower(),
        league_name=league_name,
        tournament_id=str((m.get("tournament") or {}).get("id", "")),
        match_name=m.get("name", ""),
        teams=teams,
        score=score_str,
        bo_type=bo_type,
        status=status,
    )


def _ps_parse_standings(data_list: list[dict]) -> list[StandingEntry]:
    """将 Pandascore tournament standings 转为 StandingEntry 列表。"""
    entries: list[StandingEntry] = []
    for item in data_list:
        team = item.get("team") or {}
        entries.append(StandingEntry(
            rank=item.get("rank", 0) or 0,
            team_name=team.get("name") or team.get("acronym") or "?",
            wins=item.get("wins", 0) or 0,
            losses=item.get("losses", 0) or 0,
            points=item.get("points", 0) or 0,
            status="",
        ))
    return entries


# ═══════════════════════════════════════════════════
#  端点函数
# ═══════════════════════════════════════════════════

# ── 比赛 ──

async def fetch_matches(
    league: str = "",
    status: str = "",  # running, upcoming, past
    page: int = 1,
    per_page: int = 50,
) -> ScheduleResult:
    """获取比赛列表，支持联赛和状态过滤。"""
    league_slug = _ps_league(league) if league else ""
    if league and not league_slug:
        return Failure(error=f"不支持的赛区: {league}，可用: {supported_leagues()}")

    endpoint = "/lol/matches"
    if status in ("running", "upcoming", "past"):
        endpoint = f"/lol/matches/{status}"

    params: dict[str, Any] = {
        "page": page,
        "per_page": per_page,
        "sort": "scheduled_at",
    }
    if league_slug:
        # Pandascore 使用 filter[league.name] 或 filter[league_id]
        params["filter[league.name]"] = league_slug

    result = await _ps_call(endpoint, params)
    if not result.ok:
        return Failure(error=result.error)

    data = result.value.get("data", []) if isinstance(result.value, dict) else []
    matches = _ps_parse_matches(data, league)
    return Success(value=matches)


async def fetch_running_matches(league: str = "") -> ScheduleResult:
    """获取正在进行的比赛 GET /lol/matches/running"""
    return await fetch_matches(league=league, status="running", per_page=20)


async def fetch_upcoming_matches(league: str = "", page: int = 1, per_page: int = 20) -> ScheduleResult:
    """获取即将开始的比赛 GET /lol/matches/upcoming"""
    return await fetch_matches(league=league, status="upcoming", page=page, per_page=per_page)


async def fetch_past_matches(league: str = "", page: int = 1, per_page: int = 20) -> ScheduleResult:
    """获取已结束的比赛 GET /lol/matches/past"""
    return await fetch_matches(league=league, status="past", page=page, per_page=per_page)


async def fetch_live_matches(league: str = "") -> LiveResult:
    """获取正在进行的比赛（LiveMatch 格式）GET /lol/matches/running"""
    league_slug = _ps_league(league) if league else ""
    if league and not league_slug:
        return Failure(error=f"不支持的赛区: {league}，可用: {supported_leagues()}")

    params: dict[str, Any] = {"page": 1, "per_page": 10}
    if league_slug:
        params["filter[league.name]"] = league_slug

    result = await _ps_call("/lol/matches/running", params)
    if not result.ok:
        return Failure(error=result.error)

    data = result.value.get("data", []) if isinstance(result.value, dict) else []
    matches = [_ps_parse_live_match(m, league) for m in data]
    return Success(value=matches)


async def fetch_match_detail(match_id: str) -> ScheduleResult:
    """获取单场比赛详情 GET /lol/matches/{id}"""
    result = await _ps_call(f"/lol/matches/{match_id}")
    if not result.ok:
        return Failure(error=result.error)

    data = result.value if isinstance(result.value, dict) else {}
    # 移除包装的 data 键
    if "data" in data and len(data) <= 2:
        inner = data.get("data")
        if isinstance(inner, dict):
            data = inner

    match = _ps_parse_match(data)
    return Success(value=[match])


# ── 联赛 ──

async def fetch_leagues() -> JsonResult:
    """获取所有联赛列表 GET /lol/leagues"""
    return await _ps_call("/lol/leagues", {"per_page": 100})


async def fetch_league(league_id: str) -> JsonResult:
    """获取特定联赛信息 GET /lol/leagues/{id}"""
    return await _ps_call(f"/lol/leagues/{league_id}")


# ── 系列赛 ──

async def fetch_series(league: str = "") -> JsonResult:
    """获取系列赛列表 GET /lol/series"""
    params: dict[str, Any] = {"per_page": 50}
    league_slug = _ps_league(league) if league else ""
    if league_slug:
        params["filter[league.name]"] = league_slug
    return await _ps_call("/lol/series", params)


# ── 锦标赛 ──

async def fetch_tournaments(league: str = "", status: str = "") -> JsonResult:
    """获取锦标赛列表 GET /lol/tournaments"""
    endpoint = "/lol/tournaments"
    if status in ("running", "upcoming", "past"):
        endpoint = f"/lol/tournaments/{status}"

    params: dict[str, Any] = {"per_page": 50}
    league_slug = _ps_league(league) if league else ""
    if league_slug:
        params["filter[league.name]"] = league_slug
    return await _ps_call(endpoint, params)


async def fetch_tournament(tournament_id: str) -> JsonResult:
    """获取特定锦标赛 GET /lol/tournaments/{id}"""
    return await _ps_call(f"/lol/tournaments/{tournament_id}")


async def fetch_tournament_standings(tournament_id: str) -> StandingsResult:
    """获取锦标赛积分榜 GET /lol/tournaments/{id}/standings"""
    result = await _ps_call(f"/lol/tournaments/{tournament_id}/standings", {"per_page": 50})
    if not result.ok:
        return Failure(error=result.error)

    data = result.value.get("data", []) if isinstance(result.value, dict) else []
    entries = _ps_parse_standings(data)
    return Success(value=entries)


async def fetch_tournament_matches(tournament_id: str, status: str = "") -> ScheduleResult:
    """获取锦标赛比赛列表 GET /lol/tournaments/{id}/matches"""
    endpoint = f"/lol/tournaments/{tournament_id}/matches"
    params: dict[str, Any] = {"per_page": 50}
    if status:
        endpoint = f"{endpoint}/{status}"
    result = await _ps_call(endpoint, params)
    if not result.ok:
        return Failure(error=result.error)

    data = result.value.get("data", []) if isinstance(result.value, dict) else []
    matches = _ps_parse_matches(data)
    return Success(value=matches)


# ── 战队 ──

async def fetch_teams(league: str = "", page: int = 1) -> JsonListResult:
    """获取战队列表 GET /lol/teams"""
    params: dict[str, Any] = {"page": page, "per_page": 100}
    league_slug = _ps_league(league) if league else ""
    if league_slug:
        params["filter[league.name]"] = league_slug
    result = await _ps_call("/lol/teams", params)
    if not result.ok:
        return Failure(error=result.error)
    data = result.value.get("data", []) if isinstance(result.value, dict) else []
    return Success(value=data)


async def fetch_team(team_id: str) -> JsonResult:
    """获取特定战队信息 GET /lol/teams/{id}"""
    return await _ps_call(f"/lol/teams/{team_id}")


async def fetch_team_matches(team_id: str, status: str = "") -> ScheduleResult:
    """获取战队比赛列表 GET /lol/teams/{id}/matches"""
    endpoint = f"/lol/teams/{team_id}/matches"
    if status:
        endpoint = f"{endpoint}/{status}"
    result = await _ps_call(endpoint, {"per_page": 50})
    if not result.ok:
        return Failure(error=result.error)
    data = result.value.get("data", []) if isinstance(result.value, dict) else []
    matches = _ps_parse_matches(data)
    return Success(value=matches)


# ── 选手 ──

async def fetch_players(league: str = "", page: int = 1) -> JsonListResult:
    """获取选手列表 GET /lol/players"""
    params: dict[str, Any] = {"page": page, "per_page": 100}
    league_slug = _ps_league(league) if league else ""
    if league_slug:
        params["filter[league.name]"] = league_slug
    result = await _ps_call("/lol/players", params)
    if not result.ok:
        return Failure(error=result.error)
    data = result.value.get("data", []) if isinstance(result.value, dict) else []
    return Success(value=data)


async def fetch_player(player_id: str) -> JsonResult:
    """获取特定选手信息 GET /lol/players/{id}"""
    return await _ps_call(f"/lol/players/{player_id}")


async def fetch_player_matches(player_id: str) -> ScheduleResult:
    """获取选手比赛列表 GET /lol/players/{id}/matches"""
    result = await _ps_call(f"/lol/players/{player_id}/matches", {"per_page": 50})
    if not result.ok:
        return Failure(error=result.error)
    data = result.value.get("data", []) if isinstance(result.value, dict) else []
    matches = _ps_parse_matches(data)
    return Success(value=matches)


# ═══════════════════════════════════════════════════
#  辅助 — 赛程聚合
# ═══════════════════════════════════════════════════

async def fetch_schedule(league: str = "lpl") -> ScheduleResult:
    """获取联赛赛程（等同于 upcoming + running）。"""
    return await fetch_upcoming_matches(league=league, per_page=20)


async def fetch_standings(league: str = "lpl") -> StandingsResult:
    """通过联赛名获取积分榜。

    Pandascore 的 standings 在 tournament 级别。先查 running tournaments，
    再从其中取 standings。
    """
    league_slug = _ps_league(league)
    if not league_slug:
        return Failure(error=f"不支持的赛区: {league}，可用: {supported_leagues()}")

    # 先查正在进行的锦标赛
    tn_result = await _ps_call("/lol/tournaments/running", {
        "per_page": 10,
        "filter[league.name]": league_slug,
    })
    if not tn_result.ok:
        return Failure(error=tn_result.error)

    tournaments = tn_result.value.get("data", []) if isinstance(tn_result.value, dict) else []
    if not tournaments:
        # 尝试 upcoming 锦标赛
        tn_result = await _ps_call("/lol/tournaments/upcoming", {
            "per_page": 10,
            "filter[league.name]": league_slug,
        })
        if tn_result.ok:
            tournaments = tn_result.value.get("data", []) if isinstance(tn_result.value, dict) else []

    if not tournaments:
        return Success(value=[])

    # 取第一个（最相关的）锦标赛
    tn_id = tournaments[0].get("id")
    return await fetch_tournament_standings(str(tn_id))


async def fetch_today_matches(league: str = "") -> ScheduleResult:
    """获取今日赛程。"""
    today_str = time.strftime("%Y-%m-%d")
    params: dict[str, Any] = {
        "page": 1,
        "per_page": 50,
        "sort": "scheduled_at",
        "range[scheduled_at]": f"{today_str}T00:00:00Z,{today_str}T23:59:59Z",
    }
    league_slug = _ps_league(league) if league else ""
    if league_slug:
        params["filter[league.name]"] = league_slug

    result = await _ps_call("/lol/matches/upcoming", params)
    if not result.ok:
        return Failure(error=result.error)

    data = result.value.get("data", []) if isinstance(result.value, dict) else []
    # 同时获取 running matches
    running_result = await _ps_call("/lol/matches/running", {
        "page": 1,
        "per_page": 20,
    } if not league_slug else {
        "page": 1,
        "per_page": 20,
        "filter[league.name]": league_slug,
    })
    running_data: list[dict] = []
    if running_result.ok:
        running_data = running_result.value.get("data", []) if isinstance(running_result.value, dict) else []

    all_data = running_data + data
    matches = _ps_parse_matches(all_data, league)
    return Success(value=matches)
