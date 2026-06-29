"""Common utilities for LoL plugin."""

from __future__ import annotations


def normalize_league(value: str) -> str | None:
    lowered = (value or "").strip().lower()
    supported = {
        "lck", "lpl", "lec", "lcs",
        "lco", "lcl", "ljl", "pcs", "vcs",
        "cblol", "lla", "tcl",
        "msi", "worlds",
    }
    return lowered if lowered in supported else None


def normalize_stage(value: str) -> str | None:
    lowered = (value or "").strip().lower()
    aliases = {
        "regular": "regular",
        "常规赛": "regular",
        "season": "regular",
        "playoff": "playoff",
        "淘汰赛": "playoff",
        "季后赛": "playoff",
    }
    return aliases.get(lowered)


def replace_side_mentions(text: str, team_a: str = "我方", team_b: str = "对方") -> str:
    return text.replace("我方", team_a).replace("对方", team_b).replace("蓝方", team_a).replace("红方", team_b)
