"""LoL plugin formatter package."""

from .card import (
    render_match_bp,
    render_match_detail,
    render_match_result,
    render_schedule,
    render_standings,
)
from .message import (
    format_bilibili_bp_update,
    format_bilibili_update,
    format_elimination_update,
    format_lineup_message,
    format_live_game_frame,
    format_live_list,
    format_live_match,
    format_match_bp,
    format_match_detail,
    format_match_result,
    format_post_match_summary,
    format_pre_match_preview,
    format_schedule,
    format_standings,
    format_weibo_poster,
)

__all__ = [
    # 消息格式化
    "format_schedule",
    "format_match_result",
    "format_match_bp",
    "format_match_detail",
    "format_standings",
    "format_lineup_message",
    "format_pre_match_preview",
    "format_post_match_summary",
    "format_elimination_update",
    "format_bilibili_update",
    "format_bilibili_bp_update",
    "format_weibo_poster",
    # 实时比赛
    "format_live_match",
    "format_live_game_frame",
    "format_live_list",
    # 图片渲染
    "render_schedule",
    "render_match_result",
    "render_match_bp",
    "render_match_detail",
    "render_standings",
]

