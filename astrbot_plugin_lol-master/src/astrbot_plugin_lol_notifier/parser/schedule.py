"""Parse schedule payloads into plugin model structures."""

from __future__ import annotations

from typing import Any

from ..models import LeagueMatch


def parse_schedule(raw_data: Any) -> list[LeagueMatch]:
    """Convert raw schedule data into a list of LeagueMatch models."""
    if not raw_data:
        return []
    matches: list[LeagueMatch] = []
    for item in raw_data if isinstance(raw_data, list) else [raw_data]:
        matches.append(
            LeagueMatch(
                league=str(item.get("league", "")),
                stage=str(item.get("stage", "")),
                round=str(item.get("round", "")),
                match_name=str(item.get("match_name", "")),
                bo_type=str(item.get("bo_type", "")),
                start_date=str(item.get("start_date", "")),
                start_time=str(item.get("start_time", "")),
                status=str(item.get("status", "")),
                arena=str(item.get("arena", "")),
                teams=[str(team) for team in item.get("teams", []) if team],
            )
        )
    return matches
