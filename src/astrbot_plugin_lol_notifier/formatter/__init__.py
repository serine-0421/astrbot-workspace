"""LoL plugin formatter package — 格式化层.

- message.py: 文本格式化（30+ formatter）
"""

from .message import (
    format_bilibili_bp_update,
    format_bilibili_update,
    format_daily_schedule,
    format_live_match,
    format_match_basic,
    format_match_bp,
    format_match_detail,
    format_match_games,
    format_match_players_stats,
    format_match_result,
    format_player,
    format_player_stats,
    format_players,
    format_post_match_summary,
    format_pre_match_alert,
    format_pre_match_preview,
    format_schedule,
    format_series,
    format_series_detail,
    format_standings,
    format_team_info,
    format_team_stats,
    format_tournament,
    format_tournament_teams_stats,
    format_tournaments,
)

__all__ = [
    # 赛程 & 比赛
    "format_schedule",
    "format_match_basic",
    "format_match_result",
    "format_match_bp",
    "format_match_detail",
    "format_standings",
    # 实时 & 对局
    "format_live_match",
    "format_match_games",
    # 选手 & 战队
    "format_players",
    "format_player",
    "format_player_stats",
    "format_team_info",
    "format_team_stats",
    # 系列赛 & 锦标赛
    "format_series",
    "format_series_detail",
    "format_tournaments",
    "format_tournament",
    # 统计
    "format_match_players_stats",
    "format_tournament_teams_stats",
    # 推送专用
    "format_pre_match_preview",
    "format_post_match_summary",
    # B站
    "format_bilibili_update",
    "format_bilibili_bp_update",
    "format_daily_schedule",
    "format_pre_match_alert",
]