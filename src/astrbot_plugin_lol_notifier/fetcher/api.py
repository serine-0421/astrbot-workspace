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
    # 筛选已完成的比赛
    completed = [m for m in matches if m.status in ("completed", "finished")]
    if not completed:
        return Success(value=None)

    # round_number: "last" → 最近一场已完成
    if isinstance(round_number, str) and round_number.lower() == "last":
        return Success(value=completed[-1] if completed else None)

    # 按轮次查找
    r = str(round_number)
    for m in completed:
        if m.round == r:
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

    from .lolesports import fetch_match_detail, fetch_schedule

    # 先找到 match_id
    sched = await fetch_schedule(league=league_n)
    if not sched.ok:
        return sched  # 传递原始错误
    if not sched.value:
        return Failure(error="赛程数据为空。")

    target = _pick_match(sched.value, round_number)
    if target is None:
        return Failure(error="未找到对应比赛。")

    detail = await fetch_match_detail(target.round)
    if detail is None:
        return Failure(error="无法获取比赛详情。")

    # 将 MatchDetail 包装为 LeagueMatch 以兼容 BpResult
    return Success(value=LeagueMatch(
        league=target.league,
        stage=target.stage,
        round=target.round,
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

    from .lolesports import fetch_match_detail, fetch_schedule

    sched = await fetch_schedule(league=league_n)
    if not sched.ok:
        return sched  # 传递原始错误
    if not sched.value:
        return Failure(error="赛程数据为空。")

    target = _pick_match(sched.value, round_number)
    if target is None:
        return Failure(error="未找到对应比赛。")

    detail = await fetch_match_detail(target.round)
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
    """获取今日赛程。"""
    ln = normalize_league(league) if league else None
    if league and ln is None:
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")
    from .lolesports import fetch_today_schedule
    return await fetch_today_schedule(league=ln or "")


async def get_week_schedule(league: str = "") -> JsonResult:
    """获取本周赛程。"""
    ln = normalize_league(league) if league else None
    if league and ln is None:
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")
    from .lolesports import fetch_week_schedule
    return await fetch_week_schedule(league=ln or "")


async def get_upcoming_matches(league: str, limit: int = 10) -> JsonResult:
    """获取即将到来的比赛。"""
    ln = normalize_league(league)
    if ln is None:
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")
    from .lolesports import fetch_upcoming_matches
    return await fetch_upcoming_matches(league=ln, limit=limit)


async def get_completed_matches(league: str, limit: int = 10) -> JsonResult:
    """获取已完成的比赛。"""
    ln = normalize_league(league)
    if ln is None:
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")
    from .lolesports import fetch_completed_matches
    return await fetch_completed_matches(league=ln, limit=limit)


# ═══════════════════════════════════════════════════
#  联赛信息
# ═══════════════════════════════════════════════════

async def get_all_leagues() -> JsonResult:
    """获取所有联赛列表。"""
    from .lolesports import fetch_all_leagues
    return await fetch_all_leagues()


async def get_league_details(league: str) -> JsonResult:
    """获取联赛详情。"""
    ln = normalize_league(league)
    if ln is None:
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")
    from .lolesports import fetch_league_details
    return await fetch_league_details(slug=ln)


# ═══════════════════════════════════════════════════
#  战队
# ═══════════════════════════════════════════════════

async def get_all_teams(league: str = "") -> JsonResult:
    """获取所有战队列表，可按联赛过滤。"""
    ln = normalize_league(league) if league else None
    if league and ln is None:
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")
    from .lolesports import fetch_all_teams
    return await fetch_all_teams(league=ln or "")


async def get_team(team_id: str) -> JsonResult:
    """获取单个战队信息。"""
    from .lolesports import fetch_team
    return await fetch_team(team_id=team_id)


async def get_team_roster(team_id: str) -> JsonResult:
    """获取战队阵容。"""
    from .lolesports import fetch_team_roster
    return await fetch_team_roster(team_id=team_id)


async def get_team_matches(team_id: str, limit: int = 10) -> JsonResult:
    """获取战队近期比赛。"""
    from .lolesports import fetch_team_matches
    return await fetch_team_matches(team_id=team_id, limit=limit)


async def get_team_stats(team_id: str, season: str = "current") -> JsonResult:
    """获取战队统计数据。"""
    from .lolesports import fetch_team_stats
    return await fetch_team_stats(team_id=team_id, season=season)


async def get_team_h2h(team_a: str, team_b: str) -> JsonResult:
    """获取两队交手记录。"""
    from .lolesports import fetch_team_h2h
    return await fetch_team_h2h(team_a=team_a, team_b=team_b)


async def get_team_full_profile(team_id: str) -> JsonResult:
    """获取战队完整画像（信息+阵容+统计+近期比赛）。"""
    from .lolesports import fetch_team_full_profile
    return await fetch_team_full_profile(team_id=team_id)


# ═══════════════════════════════════════════════════
#  选手
# ═══════════════════════════════════════════════════

async def get_all_players(league: str = "") -> JsonResult:
    """获取所有选手，可按联赛过滤。"""
    ln = normalize_league(league) if league else None
    if league and ln is None:
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")
    from .lolesports import fetch_all_players
    return await fetch_all_players(league=ln or "")


async def get_player(player_id: str) -> JsonResult:
    """获取单个选手信息。"""
    from .lolesports import fetch_player
    return await fetch_player(player_id=player_id)


async def get_player_stats(player_id: str, season: str = "current") -> JsonResult:
    """获取选手统计数据。"""
    from .lolesports import fetch_player_stats
    return await fetch_player_stats(player_id=player_id, season=season)


async def get_player_career(player_id: str) -> JsonResult:
    """获取选手生涯数据。"""
    from .lolesports import fetch_player_career
    return await fetch_player_career(player_id=player_id)


async def get_player_champions(player_id: str) -> JsonResult:
    """获取选手英雄池。"""
    from .lolesports import fetch_player_champions
    return await fetch_player_champions(player_id=player_id)


async def get_player_matches(player_id: str, limit: int = 10) -> JsonResult:
    """获取选手近期比赛。"""
    from .lolesports import fetch_player_matches
    return await fetch_player_matches(player_id=player_id, limit=limit)


async def get_player_full_profile(player_id: str) -> JsonResult:
    """获取选手完整画像（信息+统计+生涯+英雄池）。"""
    from .lolesports import fetch_player_full_profile
    return await fetch_player_full_profile(player_id=player_id)


# ═══════════════════════════════════════════════════
#  锦标赛
# ═══════════════════════════════════════════════════

async def get_all_tournaments(league: str = "") -> JsonResult:
    """获取所有锦标赛。"""
    ln = normalize_league(league) if league else None
    if league and ln is None:
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")
    from .lolesports import fetch_all_tournaments
    return await fetch_all_tournaments(league=ln or "")


async def get_tournament(tournament_id: str) -> JsonResult:
    """获取锦标赛详情。"""
    from .lolesports import fetch_tournament
    return await fetch_tournament(tournament_id=tournament_id)


async def get_tournament_standings(tournament_id: str) -> JsonResult:
    """获取锦标赛积分榜。"""
    from .lolesports import fetch_tournament_standings
    return await fetch_tournament_standings(tournament_id=tournament_id)


async def get_tournament_bracket(tournament_id: str) -> JsonResult:
    """获取锦标赛淘汰赛对阵。"""
    from .lolesports import fetch_tournament_bracket
    return await fetch_tournament_bracket(tournament_id=tournament_id)


async def get_tournament_mvp(tournament_id: str) -> JsonResult:
    """获取锦标赛 MVP。"""
    from .lolesports import fetch_tournament_mvp
    return await fetch_tournament_mvp(tournament_id=tournament_id)


async def get_tournament_full(tournament_id: str) -> JsonResult:
    """获取锦标赛全貌。"""
    from .lolesports import fetch_tournament_full
    return await fetch_tournament_full(tournament_id=tournament_id)


# ═══════════════════════════════════════════════════
#  英雄数据
# ═══════════════════════════════════════════════════

async def get_champion_stats(league: str = "", season: str = "current") -> JsonResult:
    """获取英雄统计数据。"""
    ln = normalize_league(league) if league else None
    if league and ln is None:
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")
    from .lolesports import fetch_champion_stats
    return await fetch_champion_stats(league=ln or "", season=season)


async def get_champion_presence(league: str = "", season: str = "current") -> JsonResult:
    """获取英雄 Pick/Ban 率。"""
    ln = normalize_league(league) if league else None
    if league and ln is None:
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")
    from .lolesports import fetch_champion_presence
    return await fetch_champion_presence(league=ln or "", season=season)


# ═══════════════════════════════════════════════════
#  排行榜
# ═══════════════════════════════════════════════════

async def get_gpr() -> JsonResult:
    """获取全球战力排名。"""
    from .lolesports import fetch_global_power_rankings
    return await fetch_global_power_rankings()


async def get_player_rankings(metric: str = "kda", limit: int = 20) -> JsonResult:
    """获取选手排名。metric: kda|kills|deaths|assists|cs"""
    from .lolesports import fetch_player_rankings
    return await fetch_player_rankings(metric=metric, limit=limit)


async def get_team_rankings(metric: str = "wins", limit: int = 20) -> JsonResult:
    """获取战队排名。"""
    from .lolesports import fetch_team_rankings
    return await fetch_team_rankings(metric=metric, limit=limit)


# ═══════════════════════════════════════════════════
#  数据排行榜
# ═══════════════════════════════════════════════════

async def get_leaderboard(metric: str, league: str = "", season: str = "current") -> JsonResult:
    """获取数据排行榜。metric: kda|kills|deaths|assists|cs|gold|vision|damage"""
    from .lolesports import (
        fetch_leaderboards_assists,
        fetch_leaderboards_cs,
        fetch_leaderboards_damage,
        fetch_leaderboards_deaths,
        fetch_leaderboards_gold,
        fetch_leaderboards_kda,
        fetch_leaderboards_kills,
        fetch_leaderboards_vision,
    )
    ln = normalize_league(league) if league else ""
    if league and not ln:
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")
    m = metric.strip().lower()
    func_map = {
        "kda": fetch_leaderboards_kda,
        "kills": fetch_leaderboards_kills,
        "deaths": fetch_leaderboards_deaths,
        "assists": fetch_leaderboards_assists,
        "cs": fetch_leaderboards_cs,
        "gold": fetch_leaderboards_gold,
        "vision": fetch_leaderboards_vision,
        "damage": fetch_leaderboards_damage,
    }
    fn = func_map.get(m)
    if fn is None:
        return Failure(error=f"不支持的数据项: {metric}，可用: {', '.join(func_map)}")
    return await fn(league=ln, season=season)


# ═══════════════════════════════════════════════════
#  搜索
# ═══════════════════════════════════════════════════

async def search_teams(query: str) -> JsonResult:
    """搜索战队。"""
    from .lolesports import search_teams
    return await search_teams(query=query)


async def search_players(query: str) -> JsonResult:
    """搜索选手。"""
    from .lolesports import search_players
    return await search_players(query=query)


async def search_tournaments(query: str) -> JsonResult:
    """搜索锦标赛。"""
    from .lolesports import search_tournaments
    return await search_tournaments(query=query)


# ═══════════════════════════════════════════════════
#  热门趋势
# ═══════════════════════════════════════════════════

async def get_trending() -> JsonResult:
    """获取热门趋势。"""
    from .lolesports import fetch_trending
    return await fetch_trending()


async def get_trending_players() -> JsonResult:
    """获取热门选手。"""
    from .lolesports import fetch_trending_players
    return await fetch_trending_players()


async def get_trending_teams() -> JsonResult:
    """获取热门战队。"""
    from .lolesports import fetch_trending_teams
    return await fetch_trending_teams()


async def get_trending_champions() -> JsonResult:
    """获取热门英雄。"""
    from .lolesports import fetch_trending_champions
    return await fetch_trending_champions()


# ═══════════════════════════════════════════════════
#  历史数据
# ═══════════════════════════════════════════════════

async def get_worlds_history() -> JsonResult:
    """获取世界赛历史。"""
    from .lolesports import fetch_worlds_history
    return await fetch_worlds_history()


async def get_msi_history() -> JsonResult:
    """获取 MSI 历史。"""
    from .lolesports import fetch_msi_history
    return await fetch_msi_history()


# ═══════════════════════════════════════════════════
#  转会 / 记录 / 奖项
# ═══════════════════════════════════════════════════

async def get_transfers(league: str = "", season: str = "current") -> JsonResult:
    """获取转会信息。"""
    ln = normalize_league(league) if league else None
    if league and ln is None:
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")
    from .lolesports import fetch_transfers
    return await fetch_transfers(league=ln or "", season=season)


async def get_records(league: str = "") -> JsonResult:
    """获取赛事记录。"""
    ln = normalize_league(league) if league else None
    if league and ln is None:
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")
    from .lolesports import fetch_records
    return await fetch_records(league=ln or "")


async def get_milestones(league: str = "") -> JsonResult:
    """获取里程碑数据。"""
    ln = normalize_league(league) if league else None
    if league and ln is None:
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")
    from .lolesports import fetch_milestones
    return await fetch_milestones(league=ln or "")


async def get_awards(league: str = "") -> JsonResult:
    """获取奖项列表。"""
    ln = normalize_league(league) if league else None
    if league and ln is None:
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")
    from .lolesports import fetch_awards
    return await fetch_awards(league=ln or "")


async def get_mvp_awards(league: str = "", season: str = "current") -> JsonResult:
    """获取 MVP 奖项。"""
    ln = normalize_league(league) if league else None
    if league and ln is None:
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")
    from .lolesports import fetch_mvp_awards
    return await fetch_mvp_awards(league=ln or "", season=season)


# ═══════════════════════════════════════════════════
#  静态数据
# ═══════════════════════════════════════════════════

async def get_static_champions() -> JsonResult:
    """获取英雄静态数据。"""
    from .lolesports import fetch_static_champions
    return await fetch_static_champions()


async def get_static_items() -> JsonResult:
    """获取装备静态数据。"""
    from .lolesports import fetch_static_items
    return await fetch_static_items()


async def get_static_patches() -> JsonResult:
    """获取版本列表。"""
    from .lolesports import fetch_static_patches
    return await fetch_static_patches()


# ═══════════════════════════════════════════════════
#  工具
# ═══════════════════════════════════════════════════

def _pick_match(matches: list[LeagueMatch], round_number: int | str) -> LeagueMatch | None:
    if isinstance(round_number, str) and round_number.lower() == "last":
        return matches[-1] if matches else None
    r = str(round_number)
    for m in matches:
        if m.round == r:
            return m
    return None
