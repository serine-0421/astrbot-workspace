"""LoL esports 数据访问层 — Pandascore 主数据源。

数据来源：Pandascore (https://api.pandascore.co) — Bearer token 鉴权

覆盖功能：
  matches (upcoming/running/past/all), match detail, standings, today,
  live, result, detail, leagues, teams, players,
  champions, items, spells, runes, masteries,
  game events, game frames, match games,
  series, tournaments, stats

内置 TTL 缓存以降低 API 调用频率。
"""

from __future__ import annotations

import time

from astrbot.api import logger

from ..models import (
    DetailResult,
    Failure,
    JsonResult,
    JsonListResult,
    LeagueMatch,
    LiveResult,
    ResultResult,
    ScheduleResult,
    StandingEntry,
    StandingsResult,
    Success,
)
from ..utils import normalize_league, normalize_stage
from .pandascore import supported_leagues

_LEAGUE_HINT = " / ".join(supported_leagues()).upper()


# ═══════════════════════════════════════════════════

# ── TTL 缓存 ──

_cache: dict[str, dict] = {}

_SCHEDULE_CACHE_TTL: float = 300.0       # 赛程 5 分钟
_STANDINGS_CACHE_TTL: float = 600.0      # 排名 10 分钟
_LIVE_CACHE_TTL: float = 45.0            # 实时 45 秒
_INFO_CACHE_TTL: float = 1200.0          # 联赛/战队 20 分钟
_SHORT_SCHEDULE_CACHE_TTL: float = 120.0 # 今日/即将 2 分钟


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
    """关闭所有 HTTP 连接池。"""
    from .pandascore import close_session as _close_ps
    await _close_ps()


# ═══════════════════════════════════════════════════
#  赛程
# ═══════════════════════════════════════════════════

async def get_schedule(
    league: str = "lpl", stage: str = "regular", season: int | str = "current"
) -> ScheduleResult:
    league_n = normalize_league(league)
    if league_n is None:
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")

    cache_key = _cache_key("schedule_ps", league_n, str(stage), str(season))
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    # 优先 Pandascore
    from .pandascore import fetch_upcoming_matches as ps_upcoming
    from .pandascore import fetch_running_matches as ps_running

    upcoming = await ps_upcoming(league=league_n, per_page=30)
    if not upcoming.ok:
        _cache_set(cache_key, upcoming, _SCHEDULE_CACHE_TTL)
        return upcoming

    # 同时拉 running 合并
    running = await ps_running(league=league_n)
    all_matches = upcoming.value or []
    if running.ok and running.value:
        all_matches = running.value + all_matches
    stage_n = normalize_stage(stage) or "regular"
    filtered = [m for m in all_matches if m.stage == stage_n or stage_n == "regular"]
    filtered = [m for m in filtered if m.status in {"live", "completed", "upcoming"} or m.status == ""]
    from .pandascore import _filter_placeholder_matches
    filtered = _filter_placeholder_matches(filtered)
    wrapped = Success(value=filtered)
    _cache_set(cache_key, wrapped, _SCHEDULE_CACHE_TTL)
    return wrapped


# ── 端点直通封装（命令与 Pandascore 端点一一对应）──

async def get_matches_upcoming(
    league: str = "", page: int = 1, per_page: int = 50
) -> ScheduleResult:
    """GET /lol/matches/upcoming — 近期赛程（合并 running 实时比赛）。"""
    from .pandascore import _filter_placeholder_matches
    from .pandascore import fetch_running_matches as ps_running
    from .pandascore import fetch_upcoming_matches as ps_upcoming

    league_key = league.strip().lower() if league else ""
    cache_key = _cache_key("upcoming", league_key, str(page))
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    upcoming = await ps_upcoming(league=league_key, page=page, per_page=per_page)
    if not upcoming.ok:
        _cache_set(cache_key, upcoming, _SCHEDULE_CACHE_TTL)
        return upcoming

    running = await ps_running(league=league_key)
    all_matches = upcoming.value or []
    if running.ok and running.value:
        all_matches = running.value + all_matches
    wrapped = Success(value=_filter_placeholder_matches(all_matches))
    _cache_set(cache_key, wrapped, _SCHEDULE_CACHE_TTL)
    return wrapped


async def get_matches_running(league: str = "") -> LiveResult:
    """GET /lol/matches/running — 正在进行的比赛（LiveMatch 格式）。"""
    from .pandascore import fetch_live_matches as ps_live
    return await ps_live(league=league.strip().lower() if league else "")


async def get_matches_past(
    league: str = "", page: int = 1, per_page: int = 50
) -> ScheduleResult:
    """GET /lol/matches/past — 已结束比赛列表。"""
    from .pandascore import fetch_past_matches as ps_past

    league_key = league.strip().lower() if league else ""
    cache_key = _cache_key("past", league_key, str(page))
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    result = await ps_past(league=league_key, page=page, per_page=per_page)
    _cache_set(cache_key, result, _SCHEDULE_CACHE_TTL)
    return result


async def get_matches_all(
    league: str = "", page: int = 1, per_page: int = 50
) -> ScheduleResult:
    """GET /lol/matches — 所有比赛（含 upcoming/running/past）。"""
    from .pandascore import _filter_placeholder_matches
    from .pandascore import fetch_matches as ps_matches

    league_key = league.strip().lower() if league else ""
    cache_key = _cache_key("all", league_key, str(page))
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    result = await ps_matches(league=league_key, page=page, per_page=per_page)
    if result.ok and result.value:
        result = Success(value=_filter_placeholder_matches(result.value))
    _cache_set(cache_key, result, _SCHEDULE_CACHE_TTL)
    return result


async def get_match_by_id(match_id: str | int) -> ScheduleResult:
    """GET /lol/matches/{id} — 按 ID 获取单场比赛详情。"""
    from .pandascore import fetch_match_detail as ps_detail

    cache_key = _cache_key("match_id", str(match_id))
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    result = await ps_detail(str(match_id))
    _cache_set(cache_key, result, _SCHEDULE_CACHE_TTL)
    return result


# ── 比赛结果 ──

async def get_match_result(
    league: str = "lpl",
    stage: str = "regular",
    round_number: int | str = "last",
    season: int | str = "current",
) -> ResultResult:
    league_n = normalize_league(league)
    if league_n is None:
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")

    # 优先 Pandascore
    from .pandascore import fetch_past_matches as ps_past
    from .pandascore import fetch_upcoming_matches as ps_upcoming
    from .pandascore import fetch_running_matches as ps_running

    # 先查已结束比赛
    past = await ps_past(league=league_n, per_page=20)
    if not past.ok:
        return past

    # Pandascore 成功（含空列表）
    matches = past.value or []
    if isinstance(round_number, str) and round_number.lower() == "last":
        completed = [m for m in matches if m.status in ("completed", "finished")]
        if completed:
            completed.sort(key=lambda m: (m.start_date, m.start_time, m.match_id), reverse=True)
            return Success(value=completed[0])
        return Success(value=matches[-1] if matches else None)
    r = str(round_number)
    for m in matches:
        if m.round == r or m.match_id == r:
            return Success(value=m)
    return Success(value=None)


# ── 比赛详情 ──

async def get_match_detail(
    league: str = "lpl",
    stage: str = "regular",
    round_number: int | str = "last",
    season: int | str = "current",
) -> DetailResult:
    league_n = normalize_league(league)
    if league_n is None:
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")

    rn_str = str(round_number)

    # 如果是 Pandascore match ID（纯数字），优先查 Pandascore
    if rn_str.isdigit() and len(rn_str) >= 5:
        from .pandascore import fetch_match_detail as ps_detail
        result = await ps_detail(rn_str)
        if result.ok:
            m = result.value[0] if result.value else None
            if m is None:
                return Failure(error=f"未找到比赛 {rn_str} 的详细信息。")
            # 转为 MatchDetail 格式
            from ..models import MatchDetail, MatchGame
            detail = MatchDetail(
                league=m.league,
                stage=m.stage,
                round=m.round,
                match_name=m.match_name,
                summary=m.summary,
                games=m.games,
            )
            return Success(value=detail)
        # Pandascore 失败
        return Failure(error=f"未找到比赛 {rn_str} 的详细信息。")

    # 先试 Pandascore（按轮次）
    from .pandascore import fetch_past_matches as ps_past
    from .pandascore import fetch_upcoming_matches as ps_upcoming

    any_ps_ok = False
    for ps_fn in [ps_past, ps_upcoming]:
        sched = await ps_fn(league=league_n, per_page=20)
        if not sched.ok:
            continue
        any_ps_ok = True
        sched_matches = sched.value or []
        target = _pick_match(sched_matches, round_number)
        if target and len(target.match_id) >= 5:
            from .pandascore import fetch_match_detail as ps_detail
            detail = await ps_detail(target.match_id)
            if detail.ok and detail.value:
                m = detail.value[0]
                from ..models import MatchDetail
                return Success(value=MatchDetail(
                    league=m.league,
                    stage=m.stage,
                    round=m.round,
                    match_name=m.match_name,
                    summary=m.summary,
                    games=m.games,
                ))

    # 所有 Pandascore 调用均失败
    if any_ps_ok:
        return Failure(error=f"未找到比赛 {rn_str} 的详细信息。")
    return Failure(error=f"无法获取比赛 {rn_str} 的详细信息。")


# ── 排名 / 积分榜 ──

async def get_standings(
    league: str = "lpl", stage: str = "regular", season: int | str = "current"
) -> StandingsResult:
    league_n = normalize_league(league)
    if league_n is None:
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")

    cache_key = _cache_key("standings_ps", league_n, str(stage), str(season))
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    # 优先 Pandascore
    from .pandascore import fetch_standings as ps_standings
    result = await ps_standings(league=league_n)
    _cache_set(cache_key, result, _STANDINGS_CACHE_TTL)
    return result


# ═══════════════════════════
#  赛程扩展
# ═══════════════════════════

async def get_today_schedule(league: str = "") -> ScheduleResult:
    """获取今日赛程。"""
    ln = normalize_league(league) if league else None
    if league and ln is None and league.strip():
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")

    cache_key = _cache_key("today_ps", ln or "")
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    # 优先 Pandascore
    from .pandascore import fetch_today_matches as ps_today
    result = await ps_today(league=ln or "")
    _cache_set(cache_key, result, _SHORT_SCHEDULE_CACHE_TTL)
    return result


async def get_daily_schedule_multi_league(league_slugs: list[str]) -> ScheduleResult:
    """获取多个联赛的今日赛程（北京时间），用于每日推送。

    league_slugs: 如 ["lpl","lck","msi","worlds"]
    """
    if not league_slugs:
        return Success(value=[])

    cache_key = _cache_key("daily_multi", ",".join(sorted(league_slugs)))
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    from .pandascore import fetch_daily_matches_multi_league as ps_daily_multi
    result = await ps_daily_multi(league_slugs)
    _cache_set(cache_key, result, _SHORT_SCHEDULE_CACHE_TTL)
    return result


def _date_today() -> str:
    from datetime import date
    return date.today().isoformat()


async def get_upcoming_schedule(league: str = "") -> JsonResult:
    """获取即将到来的赛程。"""
    ln = normalize_league(league) if league else None
    if league and ln is None:
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")

    cache_key = _cache_key("upcoming_ps", ln or "")
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    from .pandascore import fetch_upcoming_matches as ps_upcoming
    result = await ps_upcoming(league=ln or "", per_page=20)
    _cache_set(cache_key, result, _SHORT_SCHEDULE_CACHE_TTL)
    return result


# ═══════════════════════════
#  实时比赛
# ═══════════════════════════

async def get_live_matches(league: str = "") -> LiveResult:
    """获取正在进行的实时比赛。"""
    ln = normalize_league(league) if league else ""
    if league and not ln and league.strip():
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")

    cache_key = _cache_key("live_ps", ln or "")
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    # 优先 Pandascore
    from .pandascore import fetch_live_matches as ps_live
    from .pandascore import fetch_match_detail as ps_detail
    result = await ps_live(league=ln)
    if result.ok and result.value:
        for lm in result.value:
            if lm.match_id:
                detail = await ps_detail(lm.match_id)
                if detail.ok and detail.value:
                    m = detail.value[0]
                    lm.games = [{
                        "game_no": g.game_no,
                        "state": g.winner,
                        "blue_team": g.blue_team,
                        "red_team": g.red_team,
                        "winner": g.winner,
                        "duration": g.duration,
                    } for g in m.games]
    _cache_set(cache_key, result, _LIVE_CACHE_TTL)
    return result


# ═══════════════════════════
#  联赛信息
# ═══════════════════════════

async def get_all_leagues() -> JsonResult:
    """获取所有联赛列表。"""
    cache_key = _cache_key("all_leagues_ps")
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    from .pandascore import fetch_leagues as ps_leagues
    result = await ps_leagues()
    _cache_set(cache_key, result, _INFO_CACHE_TTL)
    return result


# ═══════════════════════════
#  战队
# ═══════════════════════════

async def get_all_teams(league: str = "") -> JsonListResult:
    """获取所有战队列表，可按联赛过滤。"""
    ln = normalize_league(league) if league else None
    if league and ln is None:
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")

    cache_key = _cache_key("all_teams_ps", ln or "")
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    from .pandascore import fetch_teams as ps_teams
    result = await ps_teams(league=ln or "")
    _cache_set(cache_key, result, _INFO_CACHE_TTL)
    return result


# ═══════════════════════════
#  工具
# ═══════════════════════════

def _pick_match(matches: list[LeagueMatch], round_number: int | str) -> LeagueMatch | None:
    if isinstance(round_number, str) and round_number.lower() == "last":
        completed = [m for m in matches if m.status in ("completed", "finished")]
        if completed:
            completed.sort(key=lambda m: (m.start_date, m.start_time, m.match_id), reverse=True)
            return completed[0]
        return matches[-1] if matches else None
    r = str(round_number)
    for m in matches:
        if m.round == r or m.match_id == r:
            return m
    return None


def _parse_standings_from_raw(raw: dict) -> list[StandingEntry]:
    """将原始 standings JSON 转为 StandingEntry 列表。

    兼容多种响应格式：
      - [{"rank":1, "team":{"name":"T1"}, "wins":10, ...}]
      - {"data": [...]}
      - 直接 list[dict]
    """
    data_list: list[dict] = []
    if isinstance(raw, list):
        data_list = raw
    elif isinstance(raw, dict):
        data_list = raw.get("data", raw.get("standings", raw.get("entries", [])))
        if isinstance(data_list, dict):
            data_list = list(data_list.values())
        if not isinstance(data_list, list):
            data_list = []

    entries: list[StandingEntry] = []
    for item in data_list:
        if not isinstance(item, dict):
            continue
        team = item.get("team", {}) or {}
        entries.append(StandingEntry(
            rank=item.get("rank", 0) or 0,
            team_name=team.get("name") or team.get("code") or team.get("acronym") or str(item.get("team_name", "?")),
            wins=item.get("wins", 0) or 0,
            losses=item.get("losses", 0) or 0,
            points=item.get("points", 0) or 0,
            status=item.get("status", "") or "",
        ))
    return entries


async def get_match_games(match_id: str) -> JsonResult:
    from .pandascore import fetch_match_games
    return await fetch_match_games(match_id)


# ═══════════════════════════════════════════════════
#  选手 & 战队
# ═══════════════════════════════════════════════════

async def get_players(league: str = "", page: int = 1, per_page: int = 50) -> JsonListResult:
    ln = normalize_league(league) if league else None
    if league and ln is None:
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")
    cache_key = _cache_key("players_ps", ln or "", str(page))
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .pandascore import fetch_players as ps_players
    r = await ps_players(league=ln or "", page=page, per_page=per_page)
    _cache_set(cache_key, r, _INFO_CACHE_TTL)
    return r


async def get_player(player_id: int | str) -> JsonResult:
    cache_key = _cache_key("player_ps", str(player_id))
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .pandascore import fetch_player as ps_player
    r = await ps_player(player_id)
    _cache_set(cache_key, r, _INFO_CACHE_TTL)
    return r


async def get_player_stats(player_id: int | str) -> JsonResult:
    from .pandascore import fetch_player_stats as ps_pstats
    return await ps_pstats(player_id)


# ═══════════════════════════════════════════════════
#  系列赛
# ═══════════════════════════════════════════════════

async def get_series(league: str = "", status: str = "", page: int = 1) -> JsonResult:
    ln = normalize_league(league) if league else None
    if league and ln is None:
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")
    cache_key = _cache_key("series_ps", ln or "", status, str(page))
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .pandascore import fetch_series_list
    r = await fetch_series_list(league=ln or "", status=status, page=page)
    _cache_set(cache_key, r, _SCHEDULE_CACHE_TTL)
    return r


async def get_series_detail(series_id: int | str) -> JsonResult:
    from .pandascore import fetch_series_detail
    return await fetch_series_detail(series_id)


async def get_series_teams(series_id: int | str) -> JsonResult:
    from .pandascore import fetch_series_teams
    return await fetch_series_teams(series_id)


# ═══════════════════════════════════════════════════
#  锦标赛
# ═══════════════════════════════════════════════════

async def get_tournaments(league: str = "", status: str = "") -> JsonResult:
    ln = normalize_league(league) if league else None
    if league and ln is None:
        return Failure(error=f"不支持的赛区，可用: {_LEAGUE_HINT}")
    from .pandascore import fetch_tournaments as ps_tn
    return await ps_tn(league=ln or "", status=status)


async def get_tournament(tournament_id: int | str) -> JsonResult:
    from .pandascore import fetch_tournament as ps_tn
    return await fetch_tournament(tournament_id)


# ═══════════════════════════════════════════════════
#  统计数据
# ═══════════════════════════════════════════════════

async def get_match_players_stats(match_id: str) -> JsonResult:
    from .pandascore import fetch_match_players_stats
    return await fetch_match_players_stats(match_id)


async def get_team_stats(team_id: int | str) -> JsonResult:
    from .pandascore import fetch_team_stats
    return await fetch_team_stats(team_id)


async def get_tournament_teams_stats(tournament_id: int | str) -> JsonResult:
    from .pandascore import fetch_tournament_teams_stats
    return await fetch_tournament_teams_stats(tournament_id)
