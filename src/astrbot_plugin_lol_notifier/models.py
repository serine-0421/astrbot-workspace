"""Data models for the LoL esports plugin."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, TypeVar, TypeAlias, Any

T = TypeVar("T")

# ── 通用 Result 类型 ──

@dataclass(slots=True)
class Success(Generic[T]):
    ok: bool = True
    value: T | None = None

@dataclass(slots=True)
class Failure:
    ok: bool = False
    error: str = ""

ApiResult: TypeAlias = Success[T] | Failure


# ═══════════════════════════════════════════════════
#  核心比赛模型
# ═══════════════════════════════════════════════════

@dataclass(slots=True)
class BPEntry:
    side: str = ""
    champion: str = ""
    player: str = ""
    result: str = ""

@dataclass(slots=True)
class MatchGame:
    game_no: int = 0
    blue_team: str = ""
    red_team: str = ""
    winner: str = ""
    duration: str = ""
    bp: list[BPEntry] = field(default_factory=list)

@dataclass(slots=True)
class LeagueMatch:
    league: str = ""
    stage: str = ""
    round: str = ""
    match_id: str = ""
    match_name: str = ""
    bo_type: str = ""
    start_date: str = ""
    start_time: str = ""
    status: str = ""
    arena: str = ""
    teams: list[str] = field(default_factory=list)
    team_images: list[str] = field(default_factory=list)  # 队标图片 URL
    games: list[MatchGame] = field(default_factory=list)
    summary: str = ""

@dataclass(slots=True)
class MatchDetail:
    league: str = ""
    stage: str = ""
    round: str = ""
    match_name: str = ""
    summary: str = ""
    games: list[MatchGame] = field(default_factory=list)

@dataclass(slots=True)
class StandingEntry:
    rank: int = 0
    team_name: str = ""
    wins: int = 0
    losses: int = 0
    points: int = 0
    status: str = ""


# ═══════════════════════════════════════════════════
#  实时比赛模型
# ═══════════════════════════════════════════════════

@dataclass(slots=True)
class LiveGameFrame:
    game_id: str = ""
    game_no: int = 0
    state: str = ""
    blue_team: str = ""
    red_team: str = ""
    blue_kills: int = 0
    red_kills: int = 0
    blue_gold: int = 0
    red_gold: int = 0
    blue_towers: int = 0
    red_towers: int = 0
    blue_barons: int = 0
    red_barons: int = 0
    blue_drakes: int = 0
    red_drakes: int = 0
    blue_inhibitors: int = 0
    red_inhibitors: int = 0
    game_time: str = ""
    winner: str = ""

@dataclass(slots=True)
class LiveMatch:
    match_id: str = ""
    league: str = ""
    league_name: str = ""
    tournament_id: str = ""
    match_name: str = ""
    teams: list[str] = field(default_factory=list)
    score: str = ""
    bo_type: str = ""
    status: str = ""
    games: list[LiveGameFrame] = field(default_factory=list)


# ═══════════════════════════════════════════════════
#  类型别名
# ═══════════════════════════════════════════════════

ScheduleResult: TypeAlias = Success[list[LeagueMatch]] | Failure
ResultResult: TypeAlias = Success[LeagueMatch] | Failure
DetailResult: TypeAlias = Success[MatchDetail] | Failure
StandingsResult: TypeAlias = Success[list[StandingEntry]] | Failure
LiveResult: TypeAlias = Success[list[LiveMatch]] | Failure
JsonResult: TypeAlias = Success[Any] | Failure
JsonListResult: TypeAlias = Success[list[dict[str, Any]]] | Failure
