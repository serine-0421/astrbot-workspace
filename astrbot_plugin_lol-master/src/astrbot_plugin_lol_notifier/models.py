"""Data models for the LoL esports plugin skeleton."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, TypeVar, TypeAlias

T = TypeVar("T")


@dataclass(slots=True)
class Success(Generic[T]):
    ok: bool = True
    value: T | None = None


@dataclass(slots=True)
class Failure:
    ok: bool = False
    error: str = ""


ApiResult: TypeAlias = Success[T] | Failure


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
    match_name: str = ""
    bo_type: str = ""
    start_date: str = ""
    start_time: str = ""
    status: str = ""
    arena: str = ""
    teams: list[str] = field(default_factory=list)
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


ScheduleResult: TypeAlias = Success[list[LeagueMatch]] | Failure
ResultResult: TypeAlias = Success[LeagueMatch] | Failure
BpResult: TypeAlias = Success[LeagueMatch] | Failure
DetailResult: TypeAlias = Success[MatchDetail] | Failure
StandingsResult: TypeAlias = Success[list[StandingEntry]] | Failure
