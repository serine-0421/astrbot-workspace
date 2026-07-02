"""LoL esports 数据访问层 — Pandascore 主数据源 + citoapi 备用。

数据来源优先级:
  1. Pandascore (https://api.pandascore.co) — 主数据源，Bearer token 鉴权
  2. citoapi   (https://api.citoapi.com/api/v1) — 备用数据源，x-api-key 鉴权

覆盖功能（全部优先 Pandascore，失败回退 citoapi）:
  schedule, live, result, detail, standings, today, teams, leagues,
  champions, items, spells, runes, masteries,
  game events, game frames, match games,
  players, player stats, series, tournaments,
  match/team/tournament stats

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
            from .pandascore import _filter_placeholder_matches
            filtered = _filter_placeholder_matches(filtered)
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
    filtered = [m for m in filtered if m.status in {"live", "completed", "upcoming"} or m.status == ""]
    from .pandascore import _filter_placeholder_matches
    filtered = _filter_placeholder_matches(filtered)
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
    if result.ok and isinstance(result.value, dict):
        # citoapi 返回原始 dict，需转为 StandingEntry 列表
        entries = _parse_standings_from_raw(result.value)
        result = Success(value=entries)
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
        from .pandascore import _filter_placeholder_matches
        filtered = _filter_placeholder_matches(filtered)
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


def _parse_standings_from_raw(raw: dict) -> list[StandingEntry]:
    """将 citoapi 或 Pandascore 的原始 standings JSON 转为 StandingEntry 列表。

    兼容多种响应格式：
      - {"data": [...]}  (citoapi)
      - [{"rank":1, "team":{"name":"T1"}, "wins":10, ...}]  (citoapi standings array)
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


# ═══════════════════════════════════════════════════
#  参考数据 — Champions / Items / Spells / Runes / Masteries
# ═══════════════════════════════════════════════════

_REFERENCE_CACHE_TTL: float = 3600.0  # 参考数据 1 小时


async def get_champions(version: str = "") -> JsonResult:
    cache_key = _cache_key("champions_ps", version)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .pandascore import fetch_champions
    r = await fetch_champions(version=version)
    _cache_set(cache_key, r, _REFERENCE_CACHE_TTL)
    return r


async def get_champion(champion_id: int | str) -> JsonResult:
    cache_key = _cache_key("champion_ps", str(champion_id))
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .pandascore import fetch_champion
    r = await fetch_champion(champion_id)
    _cache_set(cache_key, r, _REFERENCE_CACHE_TTL)
    return r


async def get_items(version: str = "") -> JsonResult:
    cache_key = _cache_key("items_ps", version)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .pandascore import fetch_items
    r = await fetch_items(version=version)
    _cache_set(cache_key, r, _REFERENCE_CACHE_TTL)
    return r


async def get_item(item_id: int | str) -> JsonResult:
    cache_key = _cache_key("item_ps", str(item_id))
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .pandascore import fetch_item
    r = await fetch_item(item_id)
    _cache_set(cache_key, r, _REFERENCE_CACHE_TTL)
    return r


async def get_spells() -> JsonResult:
    cache_key = _cache_key("spells_ps")
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .pandascore import fetch_spells
    r = await fetch_spells()
    _cache_set(cache_key, r, _REFERENCE_CACHE_TTL)
    return r


async def get_spell(spell_id: int | str) -> JsonResult:
    cache_key = _cache_key("spell_ps", str(spell_id))
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .pandascore import fetch_spell
    r = await fetch_spell(spell_id)
    _cache_set(cache_key, r, _REFERENCE_CACHE_TTL)
    return r


async def get_runes() -> JsonResult:
    cache_key = _cache_key("runes_ps")
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .pandascore import fetch_runes_reforged
    r = await fetch_runes_reforged()
    _cache_set(cache_key, r, _REFERENCE_CACHE_TTL)
    return r


async def get_rune_paths() -> JsonResult:
    cache_key = _cache_key("rune_paths_ps")
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .pandascore import fetch_rune_paths
    r = await fetch_rune_paths()
    _cache_set(cache_key, r, _REFERENCE_CACHE_TTL)
    return r


async def get_rune(rune_id: int | str) -> JsonResult:
    """获取单个 reforged 符文 GET /lol/runes-reforged/{id}"""
    cache_key = _cache_key("rune_ps", str(rune_id))
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .pandascore import fetch_rune_reforged
    r = await fetch_rune_reforged(rune_id)
    _cache_set(cache_key, r, _REFERENCE_CACHE_TTL)
    return r


async def get_rune_path(path_id: int | str) -> JsonResult:
    """获取单个符文路径 GET /lol/runes-reforged-paths/{id}"""
    cache_key = _cache_key("rune_path_ps", str(path_id))
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .pandascore import fetch_rune_path as ps_rune_path
    r = await ps_rune_path(path_id)
    _cache_set(cache_key, r, _REFERENCE_CACHE_TTL)
    return r


async def get_masteries() -> JsonResult:
    cache_key = _cache_key("masteries_ps")
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .pandascore import fetch_masteries
    r = await fetch_masteries()
    _cache_set(cache_key, r, _REFERENCE_CACHE_TTL)
    return r


# ═══════════════════════════════════════════════════
#  对局扩展 — Events / Frames / Match Games
# ═══════════════════════════════════════════════════

async def get_game_events(game_id: str, page: int = 1, per_page: int = 50) -> JsonResult:
    cache_key = _cache_key("game_events_ps", game_id, str(page))
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from .pandascore import fetch_game_events as ps_events
    r = await ps_events(game_id)
    _cache_set(cache_key, r, _LIVE_CACHE_TTL)
    return r


async def get_game_frames(game_id: str) -> JsonResult:
    from .pandascore import fetch_game_frames
    return await fetch_game_frames(game_id)


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
