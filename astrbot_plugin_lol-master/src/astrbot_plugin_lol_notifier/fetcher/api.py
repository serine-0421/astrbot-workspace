"""LoL data access layer for schedule, result and standings data."""

from __future__ import annotations

from ..models import (
    BpResult,
    DetailResult,
    Failure,
    ResultResult,
    ScheduleResult,
    StandingsResult,
)
from ..utils import normalize_league, normalize_stage

SUPPORTED_LEAGUES = {"lck", "lpl"}
SUPPORTED_STAGES = {"regular", "playoff"}


def _unsupported() -> Failure:
    return Failure(error="LoL 数据源尚未接入，请先补充赛事 API 实现。")


async def close_session() -> None:
    """Close any open HTTP sessions for the fetcher."""
    return None


async def get_schedule(
    league: str = "lck", stage: str = "regular", season: int | str = "current"
) -> ScheduleResult:
    if normalize_league(league) is None or normalize_stage(stage) is None:
        return Failure(error="仅支持 LCK / LPL 的常规赛或淘汰赛赛程查询。")
    return _unsupported()


async def get_match_result(
    league: str = "lck",
    stage: str = "regular",
    round_number: int | str = "last",
    season: int | str = "current",
) -> ResultResult:
    if normalize_league(league) is None or normalize_stage(stage) is None:
        return Failure(error="仅支持 LCK / LPL 的比赛结果查询。")
    return _unsupported()


async def get_match_bp(
    league: str = "lck",
    stage: str = "regular",
    round_number: int | str = "last",
    season: int | str = "current",
) -> BpResult:
    if normalize_league(league) is None or normalize_stage(stage) is None:
        return Failure(error="仅支持 LCK / LPL 的 BP 查询。")
    return _unsupported()


async def get_match_detail(
    league: str = "lck",
    stage: str = "regular",
    round_number: int | str = "last",
    season: int | str = "current",
) -> DetailResult:
    if normalize_league(league) is None or normalize_stage(stage) is None:
        return Failure(error="仅支持 LCK / LPL 的比赛详情查询。")
    return _unsupported()


async def get_standings(
    league: str = "lck", stage: str = "regular", season: int | str = "current"
) -> StandingsResult:
    if normalize_league(league) is None or normalize_stage(stage) is None:
        return Failure(error="仅支持 LCK / LPL 的积分/排名查询。")
    return _unsupported()
