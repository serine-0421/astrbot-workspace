"""Parse and normalize LoL lineup payloads."""

from __future__ import annotations

from typing import Any


def parse_lineup(raw_data: Any, team_names: tuple[str, str] | None = None) -> dict[str, Any]:
    """Normalize lineup data and replace generic sides with actual team names."""
    if raw_data is None:
        return {"lineup": [], "teams": []}

    team_a, team_b = team_names or ("蓝方", "红方")
    lineup = []
    for entry in raw_data if isinstance(raw_data, list) else [raw_data]:
        side = str(entry.get("side", ""))
        player = str(entry.get("player", ""))
        champion = str(entry.get("champion", ""))
        lineup.append(
            {
                "side": team_a if side.lower() in {"blue", "蓝方", "我方"} else team_b,
                "player": player,
                "champion": champion,
            }
        )
    return {"lineup": lineup, "teams": [team_a, team_b]}
