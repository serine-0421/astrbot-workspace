"""LoL plugin fetcher package — 数据抓取层.

三大部分:
- lolesports.py: citoapi HTTP 请求（103 个 fetch 函数, 21 个类别）
- api.py:       数据访问封装层（41 个 wrapper，league 校验 + Result 封装）
- bilibili / bilibili_dynamic / weibo: 第三方平台数据抓取
"""

from . import api, bilibili, bilibili_dynamic, lolesports, weibo
from .api import (
    close_session,
    get_all_leagues,
    get_all_players,
    get_all_teams,
    get_all_tournaments,
    get_awards,
    get_champion_presence,
    get_champion_stats,
    get_completed_matches,
    get_gpr,
    get_leaderboard,
    get_league_details,
    get_match_bp,
    get_match_detail,
    get_match_result,
    get_milestones,
    get_msi_history,
    get_mvp_awards,
    get_player,
    get_player_career,
    get_player_champions,
    get_player_full_profile,
    get_player_matches,
    get_player_rankings,
    get_player_stats,
    get_records,
    get_schedule,
    get_standings,
    get_static_champions,
    get_static_items,
    get_static_patches,
    get_team,
    get_team_full_profile,
    get_team_h2h,
    get_team_matches,
    get_team_rankings,
    get_team_roster,
    get_team_stats,
    get_today_schedule,
    get_tournament,
    get_tournament_bracket,
    get_tournament_full,
    get_tournament_mvp,
    get_tournament_standings,
    get_transfers,
    get_trending,
    get_trending_champions,
    get_trending_players,
    get_trending_teams,
    get_upcoming_matches,
    get_week_schedule,
    get_worlds_history,
    search_players,
    search_teams,
    search_tournaments,
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
    # ==================== api.py 封装层 (41) ====================
    "close_session",
    "get_schedule",
    "get_today_schedule",
    "get_week_schedule",
    "get_upcoming_matches",
    "get_completed_matches",
    "get_match_result",
    "get_match_bp",
    "get_match_detail",
    "get_standings",
    # Leagues
    "get_all_leagues",
    "get_league_details",
    # Teams
    "get_all_teams",
    "get_team",
    "get_team_roster",
    "get_team_matches",
    "get_team_stats",
    "get_team_h2h",
    "get_team_full_profile",
    # Players
    "get_all_players",
    "get_player",
    "get_player_stats",
    "get_player_career",
    "get_player_champions",
    "get_player_matches",
    "get_player_full_profile",
    # Tournaments
    "get_all_tournaments",
    "get_tournament",
    "get_tournament_standings",
    "get_tournament_bracket",
    "get_tournament_mvp",
    "get_tournament_full",
    # Champions
    "get_champion_stats",
    "get_champion_presence",
    # Rankings
    "get_gpr",
    "get_player_rankings",
    "get_team_rankings",
    # Leaderboards
    "get_leaderboard",
    # Search
    "search_teams",
    "search_players",
    "search_tournaments",
    # Trending
    "get_trending",
    "get_trending_players",
    "get_trending_teams",
    "get_trending_champions",
    # History
    "get_worlds_history",
    "get_msi_history",
    # Transfers
    "get_transfers",
    # Records & Awards
    "get_records",
    "get_milestones",
    "get_awards",
    "get_mvp_awards",
    # Static Data
    "get_static_champions",
    "get_static_items",
    "get_static_patches",
    # ==================== lolesports.py 底层 ====================
    "lolesports_close_session",
    "lolesports_get_api_key",
    "lolesports_set_api_key",
    # ==================== B 站 ====================
    "fetch_bilibili_updates",
    "fetch_bilibili_replays",
    "fetch_bilibili_live_status",
    "fetch_bilibili_comments",
    "fetch_bilibili_reply_replies",
    "fetch_blg_bp_dynamics",
    # ==================== 微博 ====================
    "fetch_weibo_posters",
    "fetch_weibo_announcements",
    "fetch_weibo_by_keyword",
]
