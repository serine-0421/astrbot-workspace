"""LoL esports 数据访问层（封装 lolesports.py 抓取结果）。

所有函数均返回 ApiResult 类型（Success | Failure），供上层命令处理器消费。
数据来源：citoapi (https://api.citoapi.com/api/v1)。
支持 14 个赛区：LCK, LPL, LEC, LCS, LCO, LCL, LJL, PCS, VCS, CBLOL, LLA, TCL, MSI, Worlds。

内置 TTL 缓存以降低 API 调用频率（每月限额 500 次）。
"""

from __future__ import annotations

import time

from ..models import (
    DetailResult,
    Failure,
    JsonResult,
    LeagueMatch,
    ResultResult,
    ScheduleResult,
    StandingsResult,
    Success,
)
from ..utils import normalize_league, normalize_stage
from .lolesports import supported_leagues

_LEAGUE_HINT = " / ".join(supported_leagues()).upper()


# ═══════════════════════════════════════════════════

# ── TTL 缓存（降低 citoapi 调用次数，每月限额 500 次） ──

# 缓存条目: {"result": ..., "ts": float}
_cache: dict[str, dict] = {}

# 赛程数据变化慢，缓存 10 分钟
_SCHEDULE_CACHE_TTL: float = 600.0
# 排名数据变化慢，缓存 15 分钟
_STANDINGS_CACHE_TTL: float = 900.0
# 实时比赛数据变化快，缓存 2 分钟
_LIVE_CACHE_TTL: float = 120.0
# 战队/选手基本信息变化较慢，缓存 30 分钟
_INFO_CACHE_TTL: float = 1800.0
# 统计数据变化中等，缓存 15 分钟
_STATS_CACHE_TTL: float = 900.0
# 今日/本周赛程变化较快，缓存 5 分钟
_SHORT_SCHEDULE_CACHE_TTL: float = 300.0


def _cache_key(*args: str) -> str:
    return ":".join(str(a) for a in args)


def _cache_get(key: str) -> dict | None:
    entry = _cache.get(key)
    if entry and (time.monotonic() - entry["ts"]) < entry.get("ttl", _SCHEDULE_CACHE_TTL):
        return entry["result"]
    return None


def _cache_set(key: str, result, ttl: float = _SCHEDULE_CACHE_TTL) -> None:
    _cache[key] = {"result": result, "ts": time.monotonic(), "ttl": ttl}


async def close_session() -> None:
    """关闭 HTTP 连接池。"""
    from .lolesports import close_session as _close

    await _close()


# ── 赛程 ──

async def get_schedule(
    league: str = "lck", stage: str = "regular", season: int | str = "current"
) -> ScheduleResult:
    league_n = normalize_league(league)
    if league_n is None:
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")

    cache_key = _cache_key("schedule", league_n, str(stage), str(season))
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    from .lolesports import fetch_schedule

    result = await fetch_schedule(league=league_n)
    if result.ok and result.value:
        # 按 stage 过滤
        stage_n = normalize_stage(stage) or "regular"
        filtered = [m for m in result.value if m.stage == stage_n or stage_n == "regular"]
        wrapped = Success(value=filtered)
    else:
        wrapped = result

    _cache_set(cache_key, wrapped, _SCHEDULE_CACHE_TTL)
    return wrapped


# ── 比赛结果 ──

async def get_match_result(
    league: str = "lck",
    stage: str = "regular",
    round_number: int | str = "last",
    season: int | str = "current",
) -> ResultResult:
    league_n = normalize_league(league)
    if league_n is None:
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")

    from .lolesports import fetch_schedule

    result = await fetch_schedule(league=league_n)
    if not result.ok:
        return result

    matches = result.value or []
    if not matches:
        return Success(value=None)

    if isinstance(round_number, str) and round_number.lower() == "last":
        completed = [m for m in matches if m.status in ("completed", "finished")]
        if completed:
            return Success(value=completed[-1])
        return Success(value=matches[-1] if matches else None)

    r = str(round_number)
    for m in matches:
        if m.round == r or m.match_id == r:
            if m.status in ("completed", "finished"):
                return Success(value=m)
    for m in matches:
        if m.round == r or m.match_id == r:
            return Success(value=m)
    return Success(value=None)


# ── 比赛详情 ──

async def get_match_detail(
    league: str = "lck",
    stage: str = "regular",
    round_number: int | str = "last",
    season: int | str = "current",
) -> DetailResult:
    league_n = normalize_league(league)
    if league_n is None:
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")

    from .lolesports import fetch_match_info, fetch_schedule

    rn_str = str(round_number)
    if rn_str.isdigit() and len(rn_str) >= 12:
        detail = await fetch_match_info(rn_str)
        if detail.ok:
            return detail
        return Failure(error=f"未找到比赛 {rn_str} 的详细信息。")

    sched = await fetch_schedule(league=league_n)
    if not sched.ok:
        return sched
    matches = sched.value or []
    if not matches:
        return Failure(error="赛程数据为空。")

    target = _pick_match(matches, round_number)
    if target is None:
        return Failure(error="未找到对应比赛。")

    match_lookup_id = target.match_id or target.round
    return await fetch_match_info(match_lookup_id)


# ── 排名 / 积分榜 ──

async def get_standings(
    league: str = "lck", stage: str = "regular", season: int | str = "current"
) -> StandingsResult:
    league_n = normalize_league(league)
    if league_n is None:
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")

    cache_key = _cache_key("standings", league_n, str(stage), str(season))
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    from .lolesports import fetch_standings

    result = await fetch_standings(league=league_n)
    _cache_set(cache_key, result, _STANDINGS_CACHE_TTL)
    return result


# ═══════════════════════════════════════════════════
#  赛程扩展
# ═══════════════════════════════════════════════════

async def get_today_schedule(league: str = "") -> JsonResult:
    """获取今日赛程（回退到主赛程数据源过滤）。"""
    ln = normalize_league(league) if league else None
    if league and ln is None and league.strip():
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")
    cache_key = _cache_key("today", ln or "")
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_schedule
    result = await fetch_schedule(league=ln or "lck")
    if result.ok and result.value:
        today = _date_today()
        filtered = [m for m in result.value if m.start_date == today]
        wrapped = Success(value=filtered)
    else:
        wrapped = result
    _cache_set(cache_key, wrapped, _SHORT_SCHEDULE_CACHE_TTL)
    return wrapped


async def get_week_schedule(league: str = "") -> JsonResult:
    """获取本周赛程（回退到主赛程数据源过滤）。"""
    ln = normalize_league(league) if league else None
    if league and ln is None and league.strip():
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")
    cache_key = _cache_key("week", ln or "")
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_schedule
    result = await fetch_schedule(league=ln or "lck")
    if result.ok and result.value:
        start, end = _date_week_range()
        filtered = [m for m in result.value if start <= m.start_date <= end]
        wrapped = Success(value=filtered)
    else:
        wrapped = result
    _cache_set(cache_key, wrapped, _SHORT_SCHEDULE_CACHE_TTL)
    return wrapped


def _date_today() -> str:
    from datetime import date
    return date.today().isoformat()


def _date_week_range() -> tuple[str, str]:
    from datetime import date, timedelta
    d = date.today()
    start = d - timedelta(days=d.weekday())
    end = start + timedelta(days=6)
    return start.isoformat(), end.isoformat()


async def get_upcoming_schedule(league: str = "") -> JsonResult:
    """获取即将到来的赛程。"""
    ln = normalize_league(league) if league else None
    if league and ln is None:
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")
    cache_key = _cache_key("upcoming", ln or "")
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_upcoming_schedule
    result = await fetch_upcoming_schedule(league=ln or "")
    _cache_set(cache_key, result, _SHORT_SCHEDULE_CACHE_TTL)
    return result


# ═══════════════════════════════════════════════════
#  联赛信息
# ═══════════════════════════════════════════════════

async def get_coverage() -> JsonResult:
    """获取直播覆盖矩阵。"""
    cache_key = _cache_key("coverage")
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_coverage
    result = await fetch_coverage()
    _cache_set(cache_key, result, _INFO_CACHE_TTL)
    return result


async def get_match_coverage(match_id: str) -> JsonResult:
    """检查单场比赛直播覆盖。"""
    cache_key = _cache_key("match_coverage", match_id)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_match_coverage
    result = await fetch_match_coverage(match_id)
    _cache_set(cache_key, result, _INFO_CACHE_TTL)
    return result


async def get_all_leagues() -> JsonResult:
    """获取所有联赛列表。"""
    cache_key = _cache_key("all_leagues")
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_all_leagues
    result = await fetch_all_leagues()
    _cache_set(cache_key, result, _INFO_CACHE_TTL)
    return result


# ═══════════════════════════════════════════════════
#  战队
# ═══════════════════════════════════════════════════

async def get_all_teams(league: str = "") -> JsonResult:
    """获取所有战队列表，可按联赛过滤。"""
    ln = normalize_league(league) if league else None
    if league and ln is None:
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")
    cache_key = _cache_key("all_teams", ln or "")
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_all_teams
    result = await fetch_all_teams(league=ln or "")
    _cache_set(cache_key, result, _INFO_CACHE_TTL)
    return result


# ═══════════════════════════════════════════════════
#  选手
# ═══════════════════════════════════════════════════


async def get_player_stats(player_id: str, season: str = "current") -> JsonResult:
    """获取选手统计数据。"""
    cache_key = _cache_key("player_stats", player_id, season)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_player_stats
    result = await fetch_player_stats(player_id=player_id, season=season)
    _cache_set(cache_key, result, _STATS_CACHE_TTL)
    return result


async def get_player_earnings_summary(player_id: str) -> JsonResult:
    """获取选手奖金汇总。"""
    cache_key = _cache_key("player_earnings_summary", player_id)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_player_earnings_summary
    result = await fetch_player_earnings_summary(player_id)
    _cache_set(cache_key, result, _INFO_CACHE_TTL)
    return result


# ═══════════════════════════════════════════════════
#  转会
# ═══════════════════════════════════════════════════

async def get_transfers(league: str = "") -> JsonResult:
    """获取转会信息。"""
    ln = normalize_league(league) if league else None
    if league and ln is None:
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")
    cache_key = _cache_key("transfers", ln or "")
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_transfers
    result = await fetch_transfers(league=ln or "")
    _cache_set(cache_key, result, _INFO_CACHE_TTL)
    return result


async def get_transfers_player(player_id: str) -> JsonResult:
    """获取选手转会历史。"""
    cache_key = _cache_key("transfers_player", player_id)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_transfers_player
    result = await fetch_transfers_player(player_id)
    _cache_set(cache_key, result, _INFO_CACHE_TTL)
    return result


async def get_transfers_team(team_slug: str) -> JsonResult:
    """获取战队转会活动。"""
    cache_key = _cache_key("transfers_team", team_slug)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_transfers_team
    result = await fetch_transfers_team(team_slug)
    _cache_set(cache_key, result, _INFO_CACHE_TTL)
    return result


# ═══════════════════════════════════════════════════
#  工具
# ═══════════════════════════════════════════════════

def _pick_match(matches: list[LeagueMatch], round_number: int | str) -> LeagueMatch | None:
    if isinstance(round_number, str) and round_number.lower() == "last":
        return matches[-1] if matches else None
    r = str(round_number)
    for m in matches:
        if m.round == r or m.match_id == r:
            return m
    return None
