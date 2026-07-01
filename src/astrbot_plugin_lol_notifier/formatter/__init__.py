"""LoL plugin formatter package — 格式化层.

- message.py: 文本格式化（14 个活跃 formatter）
"""

from .message import (
    format_bilibili_bp_update,
    format_bilibili_update,
    format_live_match,
    format_match_basic,
    format_match_bp,
    format_match_detail,
    format_match_result,
    format_post_match_summary,
    format_pre_match_preview,
    format_schedule,
    format_standings,
    format_team_info,
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
    # 战队
    "format_team_info",
    # B站 & 微博
    "format_bilibili_update",
    "format_bilibili_bp_update",
    "format_weibo_poster",
]