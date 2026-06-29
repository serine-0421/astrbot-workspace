"""LoL plugin fetcher package — 数据抓取层.

三大部分:
- lolesports.py: citoapi HTTP 请求（官方文档端点）
- api.py:       数据访问封装层（cache + league 校验 + Result 封装）
- bilibili / bilibili_dynamic / weibo: 第三方平台数据抓取
"""

from . import api, bilibili, bilibili_dynamic, lolesports, weibo
from .api import (
    close_session,
    get_all_leagues,
    get_all_teams,
    get_coverage,
    get_match_coverage,
    get_match_detail,
    get_match_result,
    get_player_earnings_summary,
    get_player_stats,
    get_schedule,
    get_standings,
    get_today_schedule,
    get_transfers,
    get_transfers_player,
    get_transfers_team,
    get_upcoming_schedule,
    get_week_schedule,
)
from .bilibili import (
    fetch_bilibili_comments,
    fetch_bilibili_live_status,
    fetch_bilibili_replays,
    fetch_bilibili_reply_replies,
    fetch_bilibili_updates,
)
from .bilibili_dynamic import fetch_blg_bp_dynamics
from .lolesports import (
    close_session as lolesports_close_session,
    get_api_key as lolesports_get_api_key,
    set_api_key as lolesports_set_api_key,
)
from .weibo import fetch_weibo_announcements, fetch_weibo_by_keyword, fetch_weibo_posters

__all__ = [
    # ==================== api.py ====================
    "close_session",
    # Schedule
    "get_schedule",
    "get_today_schedule",
    "get_week_schedule",
    "get_upcoming_schedule",
    # Matches
    "get_match_result",
    "get_match_detail",
    # Standings
    "get_standings",
    # Coverage
    "get_coverage",
    "get_match_coverage",
    # Leagues
    "get_all_leagues",
    # Teams
    "get_all_teams",
    # Players
    "get_player_stats",
    "get_player_earnings_summary",
    # Transfers
    "get_transfers",
    "get_transfers_player",
    "get_transfers_team",
    # ==================== lolesports.py ====================
    "lolesports_close_session",
    "lolesports_get_api_key",
    "lolesports_set_api_key",
    # ==================== bilibili ====================
    "fetch_bilibili_updates",
    "fetch_bilibili_live_status",
    "fetch_bilibili_replays",
    "fetch_bilibili_comments",
    "fetch_bilibili_reply_replies",
    # ==================== bilibili_dynamic ====================
    "fetch_blg_bp_dynamics",
    # ==================== weibo ====================
    "fetch_weibo_by_keyword",
    "fetch_weibo_posters",
    "fetch_weibo_announcements",
]