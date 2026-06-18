"""LoL esports 数据访问层（封装 lolesports.py 抓取结果）。

所有函数均返回 ApiResult 类型（Success | Failure），供上层命令处理器消费。
数据来源：LoL Esports 公开 API（无需 API Key）。
当前支持 LCK / LPL 的赛程、结果、BP、排名。
"""

from __future__ import annotations

from ..models import (
    BpResult,
    DetailResult,
    Failure,
    LeagueMatch,
    MatchDetail,
    ResultResult,
    ScheduleResult,
    StandingsResult,
    Success,
)
from ..utils import normalize_league, normalize_stage

SUPPORTED_LEAGUES = {"lck", "lpl"}
SUPPORTED_STAGES = {"regular", "playoff"}


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
        return Failure(error="仅支持 LCK / LPL 赛区查询。")

    from .lolesports import fetch_schedule

    result = await fetch_schedule(league=league_n)
    if result.ok and result.value:
        # 按 stage 过滤
        stage_n = normalize_stage(stage) or "regular"
        filtered = [m for m in result.value if m.stage == stage_n or stage_n == "regular"]
        return Success(value=filtered)
    return result


# ── 比赛结果 ──

async def get_match_result(
    league: str = "lck",
    stage: str = "regular",
    round_number: int | str = "last",
    season: int | str = "current",
) -> ResultResult:
    league_n = normalize_league(league)
    if league_n is None:
        return Failure(error="仅支持 LCK / LPL 赛区查询。")

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
        return Failure(error="仅支持 LCK / LPL 赛区查询。")

    from .lolesports import fetch_match_detail, fetch_schedule

    # 先找到 match_id
    sched = await fetch_schedule(league=league_n)
    if not sched.ok or not sched.value:
        return Failure(error="无法获取赛程数据。")

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
        return Failure(error="仅支持 LCK / LPL 赛区查询。")

    from .lolesports import fetch_match_detail, fetch_schedule

    sched = await fetch_schedule(league=league_n)
    if not sched.ok or not sched.value:
        return Failure(error="无法获取赛程数据。")

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
        return Failure(error="仅支持 LCK / LPL 赛区查询。")

    from .lolesports import fetch_standings

    return await fetch_standings(league=league_n)


# ── 工具 ──

def _pick_match(matches: list[LeagueMatch], round_number: int | str) -> LeagueMatch | None:
    if isinstance(round_number, str) and round_number.lower() == "last":
        return matches[-1] if matches else None
    r = str(round_number)
    for m in matches:
        if m.round == r:
            return m
    return None
