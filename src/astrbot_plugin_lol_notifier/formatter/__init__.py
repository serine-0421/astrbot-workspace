"""LoL plugin formatter package — 格式化层.

两层职责:
- message.py: 文本格式化（36 个 formatter）
- card.py:    HTML → 图片渲染
"""

from . import card, message
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
    format_champion_presence,
    format_champion_stats,
    format_elimination_update,
    format_gpr_rankings,
    format_history,
    format_json_result,
    format_leaderboard,
    format_lineup_message,
    format_live_game_frame,
    format_live_list,
    format_live_match,
    format_match_basic,
    format_match_bp,
    format_match_detail,
    format_match_result,
    format_player_champions,
    format_player_info,
    format_player_rankings,
    format_player_stats,
    format_post_match_summary,
    format_pre_match_preview,
    format_records,
    format_schedule,
    format_search_players,
    format_search_teams,
    format_standings,
    format_team_full_profile,
    format_team_info,
    format_team_matches,
    format_team_roster,
    format_tournament_bracket,
    format_tournament_info,
    format_tournament_mvp,
    format_tournament_standings,
    format_transfers,
    format_trending,
    format_weibo_poster,
)

__all__ = [
    # ==================== 消息格式化 (36) ====================
    # 核心
    "format_schedule",
    "format_match_basic",
    "format_match_result",
    "format_match_bp",
    "format_match_detail",
    "format_standings",
    # 实时
    "format_live_match",
    "format_live_game_frame",
    "format_live_list",
    # 推送
    "format_lineup_message",
    "format_pre_match_preview",
    "format_post_match_summary",
    "format_elimination_update",
    # 战队 & 选手
    "format_team_full_profile",
    "format_team_info",
    "format_team_roster",
    "format_team_matches",
    "format_player_info",
    "format_player_stats",
    "format_player_champions",
    # 锦标赛 & 英雄
    "format_tournament_info",
    "format_tournament_standings",
    "format_tournament_bracket",
    "format_tournament_mvp",
    "format_champion_stats",
    "format_champion_presence",
    # 排行 & 趋势
    "format_gpr_rankings",
    "format_player_rankings",
    "format_leaderboard",
    "format_trending",
    "format_search_teams",
    "format_search_players",
    # 历史 & 转会 & 记录
    "format_history",
    "format_transfers",
    "format_records",
    # B站 & 微博 & 通用
    "format_bilibili_update",
    "format_bilibili_bp_update",
    "format_weibo_poster",
    "format_json_result",
    # ==================== 图片渲染 ====================
    "render_schedule",
    "render_match_result",
    "render_match_bp",
    "render_match_detail",
    "render_standings",
]

