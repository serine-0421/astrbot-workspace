"""LoL esports 数据访问层（封装 lolesports.py 抓取结果）。

所有函数均返回 ApiResult 类型（Success | Failure），供上层命令处理器消费。
数据来源：citoapi (https://api.citoapi.com/api/v1)。
支持 14 个赛区：LCK, LPL, LEC, LCS, LCO, LCL, LJL, PCS, VCS, CBLOL, LLA, TCL, MSI, Worlds。

内置 TTL 缓存以降低 API 调用频率（每月限额 500 次）。
"""

from __future__ import annotations

import time

from ..models import (
    BpResult,
    DetailResult,
    Failure,
    JsonResult,
    LeagueMatch,
    MatchDetail,
    ResultResult,
    ScheduleResult,
    StandingsResult,
    Success,
)
from ..utils import normalize_league, normalize_stage
from .lolesports import supported_leagues

_LEAGUE_HINT = " / ".join(supported_leagues()).upper()

SUPPORTED_LEAGUES = {
    "lck", "lpl", "lec", "lcs",
    "lco", "lcl", "ljl", "pcs", "vcs",
    "cblol", "lla", "tcl",
    "msi", "worlds",
}
SUPPORTED_STAGES = {"regular", "playoff"}

# ── TTL 缓存（降低 citoapi 调用次数，每月限额 500 次） ──

# 缓存条目: {"result": ..., "ts": float}
_cache: dict[str, dict] = {}

# 赛程数据变化慢，缓存 10 分钟
_SCHEDULE_CACHE_TTL: float = 600.0
# 排名数据变化慢，缓存 15 分钟
_STANDINGS_CACHE_TTL: float = 900.0
# 实时比赛数据变化快，缓存 2 分钟
_LIVE_CACHE_TTL: float = 120.0
# 静态数据几乎不变，缓存 1 小时
_STATIC_CACHE_TTL: float = 3600.0
# 战队/选手基本信息变化较慢，缓存 30 分钟
_INFO_CACHE_TTL: float = 1800.0
# 统计数据变化中等，缓存 15 分钟
_STATS_CACHE_TTL: float = 900.0
# 今日/本周赛程变化较快，缓存 5 分钟
_SHORT_SCHEDULE_CACHE_TTL: float = 300.0
# 热门趋势变化较快，缓存 10 分钟
_TRENDING_CACHE_TTL: float = 600.0
# 历史数据基本不变，缓存 2 小时
_HISTORY_CACHE_TTL: float = 7200.0
# 转会/记录/奖项变化较慢，缓存 1 小时
_RECORDS_CACHE_TTL: float = 3600.0
# 排行榜数据变化中等，缓存 15 分钟
_LEADERBOARD_CACHE_TTL: float = 900.0
# 搜索缓存 10 分钟
_SEARCH_CACHE_TTL: float = 600.0
# 聚合查询缓存 10 分钟
_COMPOSITE_CACHE_TTL: float = 600.0


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

    from .lolesports import fetch_schedule, fetch_past_schedule

    async def _try_past(search_round: str | None = None) -> list:
        """回退到历史比赛。"""
        past = await fetch_past_schedule(league=league_n)
        if past.ok and past.value:
            return past.value
        return []

    result = await fetch_schedule(league=league_n)
    if not result.ok:
        return result

    matches = result.value or []
    # 当前赛程为空时，回退到历史比赛
    if not matches:
        matches = await _try_past()
    if not matches:
        return Success(value=None)

    # round_number: "last" → 最近一场已完成（找不到已完成就回退到最近一场）
    if isinstance(round_number, str) and round_number.lower() == "last":
        completed = [m for m in matches if m.status in ("completed", "finished")]
        if completed:
            return Success(value=completed[-1])
        # 当前赛程没有已完成的，查历史比赛
        if not completed:
            past_matches = await _try_past()
            if past_matches:
                past_completed = [m for m in past_matches if m.status in ("completed", "finished")]
                if past_completed:
                    return Success(value=past_completed[-1])
                return Success(value=past_matches[-1])
        # 没找到已完成的，回退到最近一场
        return Success(value=matches[-1] if matches else None)

    # 按轮次查找（先在已完成中找，再在所有中找）
    r = str(round_number)
    for m in matches:
        if m.round == r or m.match_id == r:
            if m.status in ("completed", "finished"):
                return Success(value=m)
    # 如果没找到已完成的，返回找到的（可能还没打）
    for m in matches:
        if m.round == r or m.match_id == r:
            return Success(value=m)
    # 当前赛程没找到，查历史
    past_matches = await _try_past()
    if past_matches:
        for m in past_matches:
            if m.round == r or m.match_id == r:
                if m.status in ("completed", "finished"):
                    return Success(value=m)
        for m in past_matches:
            if m.round == r or m.match_id == r:
                return Success(value=m)
    return Success(value=None)


# ── BP 阵容 ──

async def get_match_bp(
    league: str = "lck",
    stage: str = "regular",
    round_number: int | str = "last",
    season: int | str = "current",
) -> BpResult:
    league_n = normalize_league(league)
    if league_n is None:
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")

    from .lolesports import fetch_match_detail, fetch_schedule, fetch_past_schedule

    # 先找到 match_id
    sched = await fetch_schedule(league=league_n)
    if not sched.ok:
        return sched  # 传递原始错误
    matches = sched.value or []
    # 当前赛程为空时，回退到历史比赛
    if not matches:
        past = await fetch_past_schedule(league=league_n)
        if past.ok and past.value:
            matches = past.value
    if not matches:
        return Failure(error="赛程数据为空。")

    target = _pick_match(matches, round_number)
    if target is None:
        # 当前赛程没找到，尝试历史比赛（如果还没查过）
        past = await fetch_past_schedule(league=league_n)
        if past.ok and past.value:
            target = _pick_match(past.value, round_number)
    if target is None:
        return Failure(error="未找到对应比赛。")

    match_lookup_id = target.match_id or target.round
    detail = await fetch_match_detail(match_lookup_id)
    if detail is None:
        return Failure(error="无法获取比赛详情。")

    # 将 MatchDetail 包装为 LeagueMatch 以兼容 BpResult
    return Success(value=LeagueMatch(
        league=target.league,
        stage=target.stage,
        round=target.round,
        match_id=target.match_id,
        match_name=detail.match_name,
        bo_type=target.bo_type,
        start_date=target.start_date,
        start_time=target.start_time,
        status=target.status,
        teams=target.teams,
        games=detail.games,
        summary=detail.summary,
    ))


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

    from .lolesports import fetch_match_detail, fetch_schedule, fetch_past_schedule

    # round_number 是大数字 ID 时 → 直接查 match detail（跳过赛程查找）
    rn_str = str(round_number)
    if rn_str.isdigit() and len(rn_str) >= 12:
        detail = await fetch_match_detail(rn_str)
        if detail is not None:
            return Success(value=detail)
        return Failure(error=f"未找到比赛 {rn_str} 的详细信息。")

    sched = await fetch_schedule(league=league_n)
    if not sched.ok:
        return sched  # 传递原始错误
    matches = sched.value or []
    # 当前赛程为空时，回退到历史比赛
    if not matches:
        past = await fetch_past_schedule(league=league_n)
        if past.ok and past.value:
            matches = past.value
    if not matches:
        return Failure(error="赛程数据为空。")

    target = _pick_match(matches, round_number)
    if target is None:
        # 当前赛程没找到，尝试历史比赛（如果还没查过）
        past = await fetch_past_schedule(league=league_n)
        if past.ok and past.value:
            target = _pick_match(past.value, round_number)
    if target is None:
        return Failure(error="未找到对应比赛。")

    match_lookup_id = target.match_id or target.round
    detail = await fetch_match_detail(match_lookup_id)
    if detail is None:
        return Failure(error="无法获取比赛详情。")

    return Success(value=detail)


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


async def get_upcoming_matches(league: str, limit: int = 10) -> JsonResult:
    """获取即将到来的比赛。"""
    ln = normalize_league(league)
    if ln is None:
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")
    cache_key = _cache_key("upcoming", ln, str(limit))
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_upcoming_matches
    result = await fetch_upcoming_matches(league=ln, limit=limit)
    _cache_set(cache_key, result, _SHORT_SCHEDULE_CACHE_TTL)
    return result


async def get_completed_matches(league: str, limit: int = 10) -> JsonResult:
    """获取已完成的比赛。"""
    ln = normalize_league(league)
    if ln is None:
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")
    cache_key = _cache_key("completed", ln, str(limit))
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_completed_matches
    result = await fetch_completed_matches(league=ln, limit=limit)
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


async def get_league_details(league: str) -> JsonResult:
    """获取联赛详情。"""
    ln = normalize_league(league)
    if ln is None:
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")
    cache_key = _cache_key("league_detail", ln)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_league_details
    result = await fetch_league_details(slug=ln)
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


async def get_team(team_id: str) -> JsonResult:
    """获取单个战队信息。"""
    cache_key = _cache_key("team", team_id)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_team
    result = await fetch_team(team_id=team_id)
    _cache_set(cache_key, result, _INFO_CACHE_TTL)
    return result


async def get_team_roster(team_id: str) -> JsonResult:
    """获取战队阵容。"""
    cache_key = _cache_key("team_roster", team_id)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_team_roster
    result = await fetch_team_roster(team_id=team_id)
    _cache_set(cache_key, result, _INFO_CACHE_TTL)
    return result


async def get_team_matches(team_id: str, limit: int = 10) -> JsonResult:
    """获取战队近期比赛。"""
    cache_key = _cache_key("team_matches", team_id, str(limit))
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_team_matches
    result = await fetch_team_matches(team_id=team_id, limit=limit)
    _cache_set(cache_key, result, _SHORT_SCHEDULE_CACHE_TTL)
    return result


async def get_team_stats(team_id: str, season: str = "current") -> JsonResult:
    """获取战队统计数据。"""
    cache_key = _cache_key("team_stats", team_id, season)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_team_stats
    result = await fetch_team_stats(team_id=team_id, season=season)
    _cache_set(cache_key, result, _STATS_CACHE_TTL)
    return result


async def get_team_h2h(team_a: str, team_b: str) -> JsonResult:
    """获取两队交手记录。"""
    cache_key = _cache_key("team_h2h", team_a, team_b)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_team_h2h
    result = await fetch_team_h2h(team_a=team_a, team_b=team_b)
    _cache_set(cache_key, result, _STATS_CACHE_TTL)
    return result


async def get_team_full_profile(team_id: str) -> JsonResult:
    """获取战队完整画像（信息+阵容+统计+近期比赛）。"""
    cache_key = _cache_key("team_full", team_id)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_team_full_profile
    result = await fetch_team_full_profile(team_id=team_id)
    _cache_set(cache_key, result, _COMPOSITE_CACHE_TTL)
    return result


# ═══════════════════════════════════════════════════
#  选手
# ═══════════════════════════════════════════════════

async def get_all_players(league: str = "") -> JsonResult:
    """获取所有选手，可按联赛过滤。"""
    ln = normalize_league(league) if league else None
    if league and ln is None:
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")
    cache_key = _cache_key("all_players", ln or "")
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_all_players
    result = await fetch_all_players(league=ln or "")
    _cache_set(cache_key, result, _INFO_CACHE_TTL)
    return result


async def get_player(player_id: str) -> JsonResult:
    """获取单个选手信息。"""
    cache_key = _cache_key("player", player_id)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_player
    result = await fetch_player(player_id=player_id)
    _cache_set(cache_key, result, _INFO_CACHE_TTL)
    return result


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


async def get_player_career(player_id: str) -> JsonResult:
    """获取选手生涯数据。"""
    cache_key = _cache_key("player_career", player_id)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_player_career
    result = await fetch_player_career(player_id=player_id)
    _cache_set(cache_key, result, _STATS_CACHE_TTL)
    return result


async def get_player_champions(player_id: str) -> JsonResult:
    """获取选手英雄池。"""
    cache_key = _cache_key("player_champs", player_id)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_player_champions
    result = await fetch_player_champions(player_id=player_id)
    _cache_set(cache_key, result, _STATS_CACHE_TTL)
    return result


async def get_player_matches(player_id: str, limit: int = 10) -> JsonResult:
    """获取选手近期比赛。"""
    cache_key = _cache_key("player_matches", player_id, str(limit))
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_player_matches
    result = await fetch_player_matches(player_id=player_id, limit=limit)
    _cache_set(cache_key, result, _SHORT_SCHEDULE_CACHE_TTL)
    return result


async def get_player_full_profile(player_id: str) -> JsonResult:
    """获取选手完整画像（信息+统计+生涯+英雄池）。"""
    cache_key = _cache_key("player_full", player_id)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_player_full_profile
    result = await fetch_player_full_profile(player_id=player_id)
    _cache_set(cache_key, result, _COMPOSITE_CACHE_TTL)
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
#  锦标赛
# ═══════════════════════════════════════════════════

async def get_all_tournaments(league: str = "") -> JsonResult:
    """获取所有锦标赛。"""
    ln = normalize_league(league) if league else None
    if league and ln is None:
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")
    cache_key = _cache_key("all_tournaments", ln or "")
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_all_tournaments
    result = await fetch_all_tournaments(league=ln or "")
    _cache_set(cache_key, result, _INFO_CACHE_TTL)
    return result


async def get_tournament(tournament_id: str) -> JsonResult:
    """获取锦标赛详情。"""
    cache_key = _cache_key("tournament", tournament_id)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_tournament
    result = await fetch_tournament(tournament_id=tournament_id)
    _cache_set(cache_key, result, _INFO_CACHE_TTL)
    return result


async def get_tournament_standings(tournament_id: str) -> JsonResult:
    """获取锦标赛积分榜。"""
    cache_key = _cache_key("tournament_standings", tournament_id)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_tournament_standings
    result = await fetch_tournament_standings(tournament_id=tournament_id)
    _cache_set(cache_key, result, _STANDINGS_CACHE_TTL)
    return result


async def get_tournament_bracket(tournament_id: str) -> JsonResult:
    """获取锦标赛淘汰赛对阵。"""
    cache_key = _cache_key("tournament_bracket", tournament_id)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_tournament_bracket
    result = await fetch_tournament_bracket(tournament_id=tournament_id)
    _cache_set(cache_key, result, _STANDINGS_CACHE_TTL)
    return result


async def get_tournament_mvp(tournament_id: str) -> JsonResult:
    """获取锦标赛 MVP。"""
    cache_key = _cache_key("tournament_mvp", tournament_id)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_tournament_mvp
    result = await fetch_tournament_mvp(tournament_id=tournament_id)
    _cache_set(cache_key, result, _STANDINGS_CACHE_TTL)
    return result


async def get_tournament_full(tournament_id: str) -> JsonResult:
    """获取锦标赛全貌。"""
    cache_key = _cache_key("tournament_full", tournament_id)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_tournament_full
    result = await fetch_tournament_full(tournament_id=tournament_id)
    _cache_set(cache_key, result, _COMPOSITE_CACHE_TTL)
    return result


# ═══════════════════════════════════════════════════
#  英雄数据
# ═══════════════════════════════════════════════════

async def get_champion_stats(league: str = "", season: str = "current") -> JsonResult:
    """获取英雄统计数据。"""
    ln = normalize_league(league) if league else None
    if league and ln is None:
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")
    cache_key = _cache_key("champion_stats", ln or "", season)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_champion_stats
    result = await fetch_champion_stats(league=ln or "", season=season)
    _cache_set(cache_key, result, _STATS_CACHE_TTL)
    return result


async def get_champion_meta(league: str = "") -> JsonResult:
    """获取当前版本 Meta 英雄等级。"""
    ln = normalize_league(league) if league else None
    if league and ln is None:
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")
    cache_key = _cache_key("champion_meta", ln or "")
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_champion_meta
    result = await fetch_champion_meta(league=ln or "")
    _cache_set(cache_key, result, _STATS_CACHE_TTL)
    return result


# ═══════════════════════════════════════════════════
#  排行榜
# ═══════════════════════════════════════════════════

async def get_gpr() -> JsonResult:
    """获取全球战力排名。"""
    cache_key = _cache_key("gpr")
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_global_power_rankings
    result = await fetch_global_power_rankings()
    _cache_set(cache_key, result, _LEADERBOARD_CACHE_TTL)
    return result


async def get_player_rankings(metric: str = "kda", limit: int = 20) -> JsonResult:
    """获取选手排名（通过 KDA 排行榜实现）。metric: kda"""
    from .lolesports import fetch_leaderboards_kda
    m = metric.strip().lower()
    if m != "kda":
        return Failure(error=f"选手排名目前仅支持 kda 指标，收到: {metric}")
    cache_key = _cache_key("player_rankings", m, str(limit))
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    result = await fetch_leaderboards_kda()
    _cache_set(cache_key, result, _LEADERBOARD_CACHE_TTL)
    return result


async def get_team_rankings(metric: str = "wins", limit: int = 20) -> JsonResult:
    """获取战队排名。"""
    cache_key = _cache_key("team_rankings", metric, str(limit))
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_team_rankings
    result = await fetch_team_rankings(metric=metric, limit=limit)
    _cache_set(cache_key, result, _LEADERBOARD_CACHE_TTL)
    return result


# ═══════════════════════════════════════════════════
#  数据排行榜
# ═══════════════════════════════════════════════════

async def get_leaderboard(metric: str, league: str = "", season: str = "current") -> JsonResult:
    """获取数据排行榜。metric: kda|earnings|winrate|firstblood|championships"""
    from .lolesports import (
        fetch_leaderboards_championships,
        fetch_leaderboards_earnings,
        fetch_leaderboards_firstblood,
        fetch_leaderboards_kda,
        fetch_leaderboards_winrate,
    )
    ln = normalize_league(league) if league else ""
    if league and not ln:
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")
    m = metric.strip().lower()
    cache_key = _cache_key("leaderboard", m, ln, season)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    func_map = {
        "kda": fetch_leaderboards_kda,
        "earnings": fetch_leaderboards_earnings,
        "winrate": fetch_leaderboards_winrate,
        "firstblood": fetch_leaderboards_firstblood,
        "championships": fetch_leaderboards_championships,
    }
    fn = func_map.get(m)
    if fn is None:
        return Failure(error=f"不支持的数据项: {metric}，可用: {', '.join(func_map)}")
    result = await fn(league=ln, season=season)
    _cache_set(cache_key, result, _LEADERBOARD_CACHE_TTL)
    return result


# ═══════════════════════════════════════════════════
#  搜索
# ═══════════════════════════════════════════════════

async def search(query: str, category: str = "") -> JsonResult:
    """统一搜索。category: players|teams|tournaments|matches"""
    cache_key = _cache_key("search", query, category)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import search
    result = await search(query=query, category=category)
    _cache_set(cache_key, result, _SEARCH_CACHE_TTL)
    return result


# ═══════════════════════════════════════════════════
#  热门趋势
# ═══════════════════════════════════════════════════

async def get_trending() -> JsonResult:
    """获取热门趋势。"""
    cache_key = _cache_key("trending")
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_trending
    result = await fetch_trending()
    _cache_set(cache_key, result, _TRENDING_CACHE_TTL)
    return result
    _cache_set(cache_key, result, _TRENDING_CACHE_TTL)
    return result


# ═══════════════════════════════════════════════════
#  历史数据
# ═══════════════════════════════════════════════════

async def get_worlds_history() -> JsonResult:
    """获取世界赛历史。"""
    cache_key = _cache_key("worlds_history")
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_worlds_history
    result = await fetch_worlds_history()
    _cache_set(cache_key, result, _HISTORY_CACHE_TTL)
    return result


async def get_msi_history() -> JsonResult:
    """获取 MSI 历史。"""
    cache_key = _cache_key("msi_history")
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_msi_history
    result = await fetch_msi_history()
    _cache_set(cache_key, result, _HISTORY_CACHE_TTL)
    return result


# ═══════════════════════════════════════════════════
#  转会 / 记录 / 奖项
# ═══════════════════════════════════════════════════

async def get_transfers(league: str = "", season: str = "current") -> JsonResult:
    """获取转会信息。"""
    ln = normalize_league(league) if league else None
    if league and ln is None:
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")
    cache_key = _cache_key("transfers", ln or "", season)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_transfers
    result = await fetch_transfers(league=ln or "", season=season)
    _cache_set(cache_key, result, _RECORDS_CACHE_TTL)
    return result


async def get_transfers_player(player_id: str) -> JsonResult:
    """获取选手转会历史。"""
    cache_key = _cache_key("transfers_player", player_id)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_transfers_player
    result = await fetch_transfers_player(player_id)
    _cache_set(cache_key, result, _RECORDS_CACHE_TTL)
    return result


async def get_transfers_team(team_slug: str) -> JsonResult:
    """获取战队转会活动。"""
    cache_key = _cache_key("transfers_team", team_slug)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_transfers_team
    result = await fetch_transfers_team(team_slug)
    _cache_set(cache_key, result, _RECORDS_CACHE_TTL)
    return result


async def get_records(category: str = "") -> JsonResult:
    """获取赛事记录。category: milestones 等"""
    cache_key = _cache_key("records", category)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_records
    result = await fetch_records(category=category)
    _cache_set(cache_key, result, _RECORDS_CACHE_TTL)
    return result


# ═══════════════════════════════════════════════════
#  静态数据
# ═══════════════════════════════════════════════════

async def get_static_champions() -> JsonResult:
    """获取英雄静态数据。"""
    cache_key = _cache_key("static_champions")
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_static_champions
    result = await fetch_static_champions()
    _cache_set(cache_key, result, _STATIC_CACHE_TTL)
    return result


async def get_static_items() -> JsonResult:
    """获取装备静态数据。"""
    cache_key = _cache_key("static_items")
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_static_items
    result = await fetch_static_items()
    _cache_set(cache_key, result, _STATIC_CACHE_TTL)
    return result


async def get_static_patches() -> JsonResult:
    """获取版本列表。"""
    cache_key = _cache_key("static_patches")
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .lolesports import fetch_static_patches
    result = await fetch_static_patches()
    _cache_set(cache_key, result, _STATIC_CACHE_TTL)
    return result


# ═══════════════════════════════════════════════════
#  工具
# ═══════════════════════════════════════════════════

def _pick_match(matches: list[LeagueMatch], round_number: int | str) -> LeagueMatch | None:
    if isinstance(round_number, str) and round_number.lower() == "last":
        return matches[-1] if matches else None
    r = str(round_number)
    for m in matches:
        # 优先匹配 round（如 "1", "2"），其次匹配 match_id（如 API 的原始 ID）
        if m.round == r or m.match_id == r:
            return m
    return None
