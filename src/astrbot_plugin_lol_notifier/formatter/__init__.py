"""LoL plugin formatter package — 格式化层.

- message.py: 文本格式化（19 个活跃 formatter）
"""

from .message import (
    format_bilibili_bp_update,
    format_bilibili_update,
    format_coverage,
    format_live_match,
    format_match_basic,
    format_match_bp,
    format_match_detail,
    format_match_result,
    format_player_earnings,
    format_player_stats,
    format_post_match_summary,
    format_pre_match_preview,
    format_schedule,
    format_standings,
    format_team_info,
    format_transfers,
    format_transfers_player,
    format_transfers_team,
    format_weibo_poster,
)

__all__ = [
    # 赛程 & 比赛
    "format_schedule",
    "format_match_basic",
    "format_match_result",
    "format_match_bp",
    "format_match_detail",
    "format_standings",
    # 实时
    "format_live_match",
    # 推送专用
    "format_pre_match_preview",
    "format_post_match_summary",
    # 战队 & 选手
    "format_team_info",
    "format_player_stats",
    "format_player_earnings",
    # 转会 & 覆盖矩阵
    "format_transfers",
    "format_transfers_player",
    "format_transfers_team",
    "format_coverage",
    # B站 & 微博
    "format_bilibili_update",
    "format_bilibili_bp_update",
    "format_weibo_poster",
]