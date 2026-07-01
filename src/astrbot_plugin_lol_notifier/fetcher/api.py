"""LoL esports 数据访问层 — Pandascore 主数据源 + citoapi 备用。

数据来源优先级:
  1. Pandascore (https://api.pandascore.co) — 主数据源，Bearer token 鉴权
  2. citoapi   (https://api.citoapi.com/api/v1) — 备用数据源，x-api-key 鉴权

覆盖功能:
  Pandascore: schedule, live, result, detail, standings, today, teams, leagues
  citoapi:     schedule, result, detail, standings, today, live（全部为回退）

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
    StandingsResult,
    Success,
)
from ..utils import normalize_league, normalize_stage
from .lolesports import supported_leagues

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
    from .lolesports import close_session as _close_lol
    from .pandascore import close_session as _close_ps
    await _close_lol()
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
        # 仅 HTTP 错误时回退 citoapi
        logger.info(f"[api] Pandascore schedule 错误，回退 citoapi ({league_n})")
        from .lolesports import fetch_schedule as cito_schedule
        result = await cito_schedule(league=league_n)
        if result.ok and result.value:
            stage_n = normalize_stage(stage) or "regular"
            filtered = [m for m in result.value if m.stage == stage_n or stage_n == "regular"]
            wrapped = Success(value=filtered)
        else:
            wrapped = result
        _cache_set(cache_key, wrapped, _SCHEDULE_CACHE_TTL)
        return wrapped

    # 同时拉 running 合并
    running = await ps_running(league=league_n)
    all_matches = upcoming.value or []
    if running.ok and running.value:
        all_matches = running.value + all_matches
    stage_n = normalize_stage(stage) or "regular"
    filtered = [m for m in all_matches if m.stage == stage_n or stage_n == "regular"]
    wrapped = Success(value=filtered)
    _cache_set(cache_key, wrapped, _SCHEDULE_CACHE_TTL)
    return wrapped


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
        # 仅 HTTP 错误时回退 citoapi
        logger.info(f"[api] Pandascore match_result 错误，回退 citoapi ({league_n})")
        from .lolesports import fetch_schedule as cito_schedule
        result = await cito_schedule(league=league_n)
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

    # Pandascore 成功（含空列表）
    matches = past.value or []
    if isinstance(round_number, str) and round_number.lower() == "last":
        completed = [m for m in matches if m.status in ("completed", "finished")]
        if completed:
            return Success(value=completed[-1])
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
        # 仅 HTTP 错误时回退 citoapi
        logger.info(f"[api] Pandascore detail {rn_str} 错误，回退 citoapi")
        from .lolesports import _parse_full_match_detail, fetch_match_info
        detail = await fetch_match_info(rn_str)
        if detail.ok and isinstance(detail.value, dict):
            return Success(value=_parse_full_match_detail(detail.value, league_n))
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

    # Pandascore 成功返回但无匹配 → 不查 citoapi，直接报未找到
    if any_ps_ok:
        return Failure(error=f"未找到比赛 {rn_str} 的详细信息。")

    # 所有 Pandascore 调用均失败 → 回退 citoapi
    logger.info(f"[api] Pandascore detail 全部错误，回退 citoapi ({league_n})")
    from .lolesports import _parse_full_match_detail, fetch_match_info, fetch_schedule as cito_schedule
    sched = await cito_schedule(league=league_n)
    if not sched.ok:
        return sched
    matches = sched.value or []
    if not matches:
        return Failure(error="赛程数据为空。")
    target = _pick_match(matches, round_number)
    if target is None:
        return Failure(error="未找到对应比赛。")
    match_lookup_id = target.match_id or target.round
    detail = await fetch_match_info(match_lookup_id)
    if detail.ok and isinstance(detail.value, dict):
        return Success(value=_parse_full_match_detail(detail.value, league_n))
    return detail


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
    if result.ok:
        _cache_set(cache_key, result, _STANDINGS_CACHE_TTL)
        return result

    # 回退 citoapi
    logger.info(f"[api] Pandascore standings 失败，回退 citoapi ({league_n})")
    from .lolesports import fetch_standings as cito_standings
    result = await cito_standings(league=league_n)
    _cache_set(cache_key, result, _STANDINGS_CACHE_TTL)
    return result


# ═══════════════════════════════════════════════════
#  赛程扩展
# ═══════════════════════════════════════════════════

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
    if result.ok:
        _cache_set(cache_key, result, _SHORT_SCHEDULE_CACHE_TTL)
        return result

    # 仅 HTTP 错误时回退 citoapi
    logger.info(f"[api] Pandascore today 错误，回退 citoapi ({ln or ''})")
    from .lolesports import fetch_schedule as cito_schedule
    result = await cito_schedule(league=ln or "lpl")
    if result.ok and result.value:
        today = _date_today()
        filtered = [m for m in result.value if m.start_date == today]
        wrapped = Success(value=filtered)
    else:
        wrapped = result
    _cache_set(cache_key, wrapped, _SHORT_SCHEDULE_CACHE_TTL)
    return wrapped


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
    if result.ok:
        _cache_set(cache_key, result, _SHORT_SCHEDULE_CACHE_TTL)
        return result

    # 仅 HTTP 错误时回退 citoapi
    logger.info(f"[api] Pandascore upcoming 错误，回退 citoapi ({ln or ''})")
    from .lolesports import fetch_upcoming_schedule as cito_upcoming
    result = await cito_upcoming(league=ln or "")
    _cache_set(cache_key, result, _SHORT_SCHEDULE_CACHE_TTL)
    return result


# ═══════════════════════════════════════════════════
#  实时比赛（Pandascore 主要修复目标）
# ═══════════════════════════════════════════════════

async def get_live_matches(league: str = "") -> LiveResult:
    """获取正在进行的实时比赛。优先 Pandascore，失败回退 citoapi。"""
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
    if result.ok:
        # 填充详细信息
        if result.value:
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

    # 仅 HTTP 错误时回退 citoapi
    logger.info(f"[api] Pandascore live 错误，回退 citoapi ({ln or ''})")
    from .lolesports import fetch_live_match_details, fetch_live_matches as cito_live
    result = await cito_live(ln if ln else None)
    if result.ok and result.value:
        for lm in result.value:
            await fetch_live_match_details(lm)
    _cache_set(cache_key, result, _LIVE_CACHE_TTL)
    return result


# ═══════════════════════════════════════════════════
#  联赛信息
# ═══════════════════════════════════════════════════

async def get_all_leagues() -> JsonResult:
    """获取所有联赛列表。"""
    cache_key = _cache_key("all_leagues_ps")
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    from .pandascore import fetch_leagues as ps_leagues
    result = await ps_leagues()
    if result.ok:
        _cache_set(cache_key, result, _INFO_CACHE_TTL)
        return result

    logger.info("[api] Pandascore leagues 失败，回退 citoapi")
    from .lolesports import fetch_all_leagues
    result = await fetch_all_leagues()
    _cache_set(cache_key, result, _INFO_CACHE_TTL)
    return result


# ═══════════════════════════════════════════════════
#  战队
# ═══════════════════════════════════════════════════

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
    if result.ok:
        _cache_set(cache_key, result, _INFO_CACHE_TTL)
        return result

    logger.info(f"[api] Pandascore teams 失败，回退 citoapi ({ln or ''})")
    from .lolesports import fetch_all_teams
    result = await fetch_all_teams(league=ln or "")
    _cache_set(cache_key, result, _INFO_CACHE_TTL)
    return result


# ═══════════════════════════════════════════════════
#  对局
# ═══════════════════════════════════════════════════

async def get_game_detail(game_id: str) -> JsonResult:
    """获取单局详情 GET /lol/games/{id}。"""
    from .pandascore import fetch_game_detail as ps_game
    return await ps_game(game_id)


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
