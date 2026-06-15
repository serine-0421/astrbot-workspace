"""LoL esports API skeleton.

This module defines the future data-access boundary for LCK / LPL schedule,
result, BP, detail, and standings queries. The current version validates
league/stage inputs and returns a clear not-implemented error so the plugin
structure can be wired first and the actual data source can be added later.
"""

from __future__ import annotations

from .models import (
    BpResult,
    DetailResult,
    Failure,
    ResultResult,
    ScheduleResult,
    StandingsResult,
)

SUPPORTED_LEAGUES = {"lck", "lpl"}
SUPPORTED_STAGES = {"regular", "playoff"}


def _normalize_league(value: str) -> str | None:
    lowered = (value or "").strip().lower()
    return lowered if lowered in SUPPORTED_LEAGUES else None


def _normalize_stage(value: str) -> str | None:
    lowered = (value or "").strip().lower()
    aliases = {
        "regular": "regular",
        "常规赛": "regular",
        "season": "regular",
        "playoff": "playoff",
        "淘汰赛": "playoff",
        "季后赛": "playoff",
    }
    normalized = aliases.get(lowered)
    return normalized if normalized in SUPPORTED_STAGES else None


async def close_session() -> None:
    """Kept for compatibility with the plugin lifecycle."""
    return None


def _unsupported() -> Failure:
    return Failure(error="LoL 数据源尚未接入，请先补充赛事 API 实现。")


async def get_schedule(
    league: str = "lck", stage: str = "regular", season: int | str = "current"
) -> ScheduleResult:
    if _normalize_league(league) is None or _normalize_stage(stage) is None:
        return Failure(error="仅支持 LCK / LPL 的常规赛或淘汰赛赛程查询。")
    return _unsupported()


async def get_match_result(
    league: str = "lck",
    stage: str = "regular",
    round_number: int | str = "last",
    season: int | str = "current",
) -> ResultResult:
    if _normalize_league(league) is None or _normalize_stage(stage) is None:
        return Failure(error="仅支持 LCK / LPL 的比赛结果查询。")
    return _unsupported()


async def get_match_bp(
    league: str = "lck",
    stage: str = "regular",
    round_number: int | str = "last",
    season: int | str = "current",
) -> BpResult:
    if _normalize_league(league) is None or _normalize_stage(stage) is None:
        return Failure(error="仅支持 LCK / LPL 的 BP 查询。")
    return _unsupported()


async def get_match_detail(
    league: str = "lck",
    stage: str = "regular",
    round_number: int | str = "last",
    season: int | str = "current",
) -> DetailResult:
    if _normalize_league(league) is None or _normalize_stage(stage) is None:
        return Failure(error="仅支持 LCK / LPL 的比赛详情查询。")
    return _unsupported()


async def get_standings(
    league: str = "lck", stage: str = "regular", season: int | str = "current"
) -> StandingsResult:
    if _normalize_league(league) is None or _normalize_stage(stage) is None:
        return Failure(error="仅支持 LCK / LPL 的积分/排名查询。")
    return _unsupported()
