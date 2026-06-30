"""LoL Esports 数据抓取器 — citoapi 封装。

数据来源：citoapi (https://api.citoapi.com/api/v1)

端点映射（旧 Riot API → 新 citoapi）：
  赛程:    getSchedule          → GET /lol/leagues/{slug}/schedule
  排名:    getStandings         → GET /lol/leagues/{slug}/standings
  实时:    getLive              → GET /lol/live
  详情:    getEventDetails      → GET /lol/matches/{matchId}
  实时帧:  feed.lolesports.com  → GET /lol/live/{gameId}/window
"""

from __future__ import annotations

import asyncio
import time
import traceback
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from astrbot.api import logger

from ..models import (
    Failure,
    JsonListResult,
    JsonResult,
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

_BEIJING_TZ = timezone(timedelta(hours=8))  # UTC+8 北京时间

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
    # 常见锦标赛别名
    "msi2024": "lol-msi-2024",
    "msi2023": "lol-msi-2023",
    "worlds2024": "lol-worlds-2024",
    "worlds2023": "lol-worlds-2023",
    "worlds2022": "lol-worlds-2022",
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
#  Schedule & Standings（赛程 & 积分榜）
# ═══════════════════════════════════════════════════

async def fetch_schedule(league: str = "lck") -> ScheduleResult:
    """获取联赛赛程 GET /lol/leagues/{cito}/schedule"""
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


async def fetch_standings(league: str = "lck") -> JsonResult:
    """获取联赛积分榜 GET /lol/leagues/{cito}/standings"""
    slug = (league or "").strip().lower()
    cito = _cito_slug(slug)
    if not cito:
        return Failure(error=f"不支持的赛区: {slug}，可用: {supported_leagues()}")
    return await _api_call(f"/lol/leagues/{cito}/standings")


async def fetch_today_schedule(league: str = "") -> JsonResult:
    """获取今日赛程 GET /lol/schedule/today"""
    params: dict[str, str] = {}
    if league:
        params["league"] = _resolve_slug(league)
    return await _api_call("/lol/schedule/today", params)


async def fetch_upcoming_schedule(league: str = "") -> JsonResult:
    """获取即将到来的赛程 GET /lol/schedule/upcoming"""
    params: dict[str, str] = {}
    if league:
        params["league"] = _resolve_slug(league)
    return await _api_call("/lol/schedule/upcoming", params)


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
#  Leagues（联赛）
# ═══════════════════════════════════════════════════

async def fetch_all_leagues() -> JsonResult:
    """获取所有联赛列表 GET /lol/leagues"""
    return await _api_call("/lol/leagues")


# ═══════════════════════════════════════════════════
#  Live（实时比赛）
# ═══════════════════════════════════════════════════

async def fetch_coverage() -> JsonResult:
    """获取直播覆盖矩阵 GET /lol/coverage"""
    return await _api_call("/lol/coverage")


async def fetch_matches_live() -> JsonResult:
    """获取所有正在进行的比赛 GET /lol/matches/live"""
    return await _api_call("/lol/matches/live")


async def fetch_match_coverage(match_id: str) -> JsonResult:
    """检查单场比赛直播覆盖 GET /lol/matches/{matchId}/coverage"""
    return await _api_call(f"/lol/matches/{match_id}/coverage")


async def fetch_live_series(match_id: str) -> JsonResult:
    """获取实时系列赛状态 GET /lol/live/{matchId}/series"""
    return await _api_call(f"/lol/live/{match_id}/series")


async def fetch_live_visual_state(game_id: str) -> JsonResult:
    """获取实时视觉状态 GET /lol/live/{gameId}/visual-state"""
    return await _api_call(f"/lol/live/{game_id}/visual-state")


# ═══════════════════════════════════════════════════
#  Matches & Games（比赛 & 对局）
# ═══════════════════════════════════════════════════

async def fetch_match_info(match_id: str) -> JsonResult:
    """获取比赛基本信息 GET /lol/matches/{matchId}"""
    return await _api_call(f"/lol/matches/{match_id}")


async def fetch_match_games(match_id: str) -> JsonResult:
    """获取比赛的各局 GET /lol/matches/{matchId}/games"""
    return await _api_call(f"/lol/matches/{match_id}/games")


async def fetch_game_info(game_id: str) -> JsonResult:
    """获取单局比赛信息 GET /lol/games/{gameId}"""
    return await _api_call(f"/lol/games/{game_id}")


async def fetch_game_stats(game_id: str) -> JsonResult:
    """获取单局统计数据 GET /lol/games/{gameId}/stats"""
    return await _api_call(f"/lol/games/{game_id}/stats")


async def fetch_game_player_stats(game_id: str) -> JsonResult:
    """获取单局选手统计 GET /lol/games/{gameId}/player-stats"""
    return await _api_call(f"/lol/games/{game_id}/player-stats")


async def fetch_game_postgame(game_id: str) -> JsonResult:
    """获取单局赛后数据 GET /lol/games/{gameId}/postgame"""
    return await _api_call(f"/lol/games/{game_id}/postgame")


async def fetch_game_plates(game_id: str) -> JsonResult:
    """获取单局塔皮数据 GET /lol/games/{gameId}/plates"""
    return await _api_call(f"/lol/games/{game_id}/plates")


async def fetch_game_distributions(game_id: str) -> JsonResult:
    """获取单局经济/伤害分布 GET /lol/games/{gameId}/distributions"""
    return await _api_call(f"/lol/games/{game_id}/distributions")


async def fetch_game_vision(game_id: str) -> JsonResult:
    """获取单局视野数据 GET /lol/games/{gameId}/vision"""
    return await _api_call(f"/lol/games/{game_id}/vision")


async def fetch_game_jungle_share(game_id: str) -> JsonResult:
    """获取单局打野资源占比 GET /lol/games/{gameId}/jungle-share"""
    return await _api_call(f"/lol/games/{game_id}/jungle-share")


# ═══════════════════════════════════════════════════
#  Teams（战队）
# ═══════════════════════════════════════════════════

async def fetch_all_teams(league: str = "") -> JsonResult:
    """获取所有战队 GET /lol/teams"""
    params: dict[str, str] = {}
    if league:
        params["league"] = _resolve_slug(league)
    return await _api_call("/lol/teams", params)


async def fetch_team_roster_history(team_slug: str) -> JsonResult:
    """获取战队历史阵容 GET /lol/teams/{slug}/roster/history"""
    return await _api_call(f"/lol/teams/{team_slug}/roster/history")


async def fetch_team_objectives(team_slug: str, last: int = 10) -> JsonResult:
    """获取战队目标控制率 GET /lol/teams/{slug}/objectives"""
    return await _api_call(f"/lol/teams/{team_slug}/objectives", {"last": str(last)})


# ═══════════════════════════════════════════════════
#  Players（选手）
# ═══════════════════════════════════════════════════

async def fetch_player_stats(player_id: str, season: str = "current") -> JsonResult:
    """获取选手统计数据 GET /lol/players/{playerId}/stats"""
    return await _api_call(f"/lol/players/{player_id}/stats", {"season": season})


async def fetch_player_form(player_id: str, windows: int = 10, league: str = "") -> JsonResult:
    """获取选手近期状态 GET /lol/players/{playerId}/form"""
    params: dict[str, str] = {"windows": str(windows)}
    if league:
        params["league"] = _resolve_slug(league)
    return await _api_call(f"/lol/players/{player_id}/form", params)


async def fetch_player_champion_pool(player_id: str, last: int = 20, league: str = "") -> JsonResult:
    """获取选手英雄池 GET /lol/players/{playerId}/champion-pool"""
    params: dict[str, str] = {"last": str(last)}
    if league:
        params["league"] = _resolve_slug(league)
    return await _api_call(f"/lol/players/{player_id}/champion-pool", params)


async def fetch_player_earnings(player_id: str) -> JsonResult:
    """获取选手奖金 GET /lol/players/{playerId}/earnings"""
    return await _api_call(f"/lol/players/{player_id}/earnings")


async def fetch_player_earnings_summary(player_id: str) -> JsonResult:
    """获取选手奖金汇总 GET /lol/players/{playerId}/earnings/summary"""
    return await _api_call(f"/lol/players/{player_id}/earnings/summary")


async def fetch_player_teams(player_id: str) -> JsonResult:
    """获取选手队伍历史 GET /lol/players/{playerId}/teams"""
    return await _api_call(f"/lol/players/{player_id}/teams")


# ═══════════════════════════════════════════════════
#  Transfers（转会）
# ═══════════════════════════════════════════════════

async def fetch_transfers(league: str = "") -> JsonResult:
    """获取转会列表 GET /lol/transfers"""
    params: dict[str, str] = {}
    if league:
        params["league"] = _resolve_slug(league)
    return await _api_call("/lol/transfers", params)


async def fetch_transfers_player(player_id: str) -> JsonResult:
    """获取选手转会记录 GET /lol/transfers/player/{playerId}"""
    return await _api_call(f"/lol/transfers/player/{player_id}")


async def fetch_transfers_team(team_slug: str) -> JsonResult:
    """获取战队转会记录 GET /lol/transfers/team/{slug}"""
    return await _api_call(f"/lol/transfers/team/{team_slug}")


# ═══════════════════════════════════════════════════
#  Webhooks（事件订阅）
# ═══════════════════════════════════════════════════

async def fetch_webhook_events() -> JsonResult:
    """获取 Webhook 事件类型列表 GET /lol/webhooks/events"""
    return await _api_call("/lol/webhooks/events")


# ═══════════════════════════════════════════════════
#  实时比赛解析 — GET /lol/live
# ═══════════════════════════════════════════════════

async def fetch_live_matches(league: str | None = None) -> LiveResult:
    """获取所有正在进行的比赛（解析为 LiveMatch 列表）GET /lol/live"""
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
            tournament_id="",
            match_name=" vs ".join(teams) if teams else ev.get("name", ""),
            teams=teams,
            score=f"{blue_wins}:{red_wins}",
            bo_type=f"BO{bo}" if bo else "",
            status=m.get("state", m.get("status", "")),
            games=games,
        ))

    return Success(value=live_matches)


async def fetch_live_match_details(live_match: LiveMatch) -> None:
    """为 LiveMatch 补充实时比赛详情（游戏内状态 — 击杀/经济/塔/龙）。
    
    fetch_live_matches 已提供基础对局信息；此函数尝试获取 visualState 数据。
    如果 API 不可用则静默跳过，不影响基础显示。
    """
    for game in live_match.games:
        if not game.game_id:
            continue
        try:
            result = await fetch_live_visual_state(game.game_id)
            if result.ok and isinstance(result.value, dict):
                vs = result.value
                game.game_time = vs.get("gameTime", vs.get("game_time", ""))
                # 双方数据常嵌套在 teams 数组中
                vteams = vs.get("teams", [])
                for vt in vteams:
                    side = vt.get("side", "").lower()
                    if side == "blue":
                        game.blue_kills = vt.get("kills", 0)
                        game.blue_gold = vt.get("gold", 0)
                        game.blue_towers = vt.get("towers", 0)
                        game.blue_barons = vt.get("barons", 0)
                        game.blue_drakes = vt.get("dragons", vt.get("drakes", 0))
                        game.blue_inhibitors = vt.get("inhibitors", 0)
                    elif side == "red":
                        game.red_kills = vt.get("kills", 0)
                        game.red_gold = vt.get("gold", 0)
                        game.red_towers = vt.get("towers", 0)
                        game.red_barons = vt.get("barons", 0)
                        game.red_drakes = vt.get("dragons", vt.get("drakes", 0))
                        game.red_inhibitors = vt.get("inhibitors", 0)
        except Exception:
            pass


def _parse_full_match_detail(data: dict, league_slug: str = "") -> MatchDetail:
    """将 citoapi /lol/matches/{id} 返回的 JSON 解析为 MatchDetail。"""
    from ..models import BPEntry

    # 提取 match 层级（可能被嵌套在 "match" 或 "data" 键下）
    m = data.get("match", data.get("data", data))
    if isinstance(m, list):
        m = m[0] if m else {}

    games_raw = m.get("games", data.get("games", []))
    if not isinstance(games_raw, list) and isinstance(m, dict):
        games_raw = m.get("games", [])
    games: list[MatchGame] = []
    for g in games_raw:
        gteams = g.get("teams", [])
        blue = _pick_side(gteams, "blue")
        red = _pick_side(gteams, "red")
        winner_side = g.get("winner", g.get("winningTeam", ""))
        if winner_side == "blue":
            winner_name = blue.get("name", blue.get("code", ""))
        elif winner_side == "red":
            winner_name = red.get("name", red.get("code", ""))
        else:
            winner_name = str(winner_side) if winner_side else ""

        # 解析 BP（picks/bans）
        bp_list: list[BPEntry] = []
        # citoapi 可能用 "picks" 或 "picksBans" 或 "bans"
        for pick in g.get("picks", g.get("picksBans", g.get("bans", []))):
            bp_list.append(BPEntry(
                side=pick.get("side", ""),
                champion=pick.get("champion", pick.get("championId", "")),
                player=pick.get("player", pick.get("summonerName", "")),
                result=pick.get("result", pick.get("won", "")),
            ))

        games.append(MatchGame(
            game_no=g.get("number", g.get("gameNo", g.get("game_no", 0))),
            blue_team=blue.get("name", blue.get("code", "蓝方")),
            red_team=red.get("name", red.get("code", "红方")),
            winner=winner_name,
            duration=_format_duration(g.get("duration", g.get("gameLength", 0))),
            bp=bp_list,
        ))

    # 提取 match name / teams
    teams = m.get("teams", data.get("teams", []))
    match_name = m.get("name", data.get("name", ""))
    if not match_name and isinstance(teams, list) and len(teams) >= 2:
        tnames = [
            t.get("name", t.get("code", "?"))
            for t in teams
        ]
        match_name = " vs ".join(tnames)

    return MatchDetail(
        league=league_slug.upper() if league_slug else str(m.get("league", data.get("league", ""))).upper(),
        stage=m.get("stage", m.get("type", data.get("stage", ""))),
        round=str(m.get("number", m.get("round", data.get("round", "")))),
        match_name=match_name,
        summary=m.get("summary", data.get("summary", "")),
        games=games,
    )


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

    round_val = (
        str(m.get("number", m.get("matchNumber", m.get("round", ""))))
        or str(ev.get("number", ev.get("matchNumber", ev.get("round", ""))))
        or str(m.get("id", ev.get("id", "")))
    )

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
#  工具函数
# ═══════════════════════════════════════════════════

def _parse_iso(iso_str: str | int | float) -> tuple[str, str]:
    """将 citoapi 时间戳统一转为北京时间 (UTC+8) 的 (日期, 时间) 元组。"""
    if not iso_str:
        return ("", "")
    try:
        if isinstance(iso_str, (int, float)):
            # Unix 时间戳 → UTC → 北京时间
            dt = datetime.fromtimestamp(iso_str, tz=timezone.utc)
        elif str(iso_str).isdigit():
            ts = int(iso_str)
            dt = datetime.fromtimestamp(ts / 1000 if ts > 1e12 else ts, tz=timezone.utc)
        else:
            # ISO 8601 字符串，citoapi 返回 UTC 时间
            s = str(iso_str).replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
        beijing = dt.astimezone(_BEIJING_TZ)
        return (beijing.strftime("%Y-%m-%d"), beijing.strftime("%H:%M"))
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



