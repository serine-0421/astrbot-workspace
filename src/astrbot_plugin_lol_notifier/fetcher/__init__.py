"""LoL plugin fetcher package — 数据抓取层.

架构:
- pandascore.py:  Pandascore HTTP 客户端（主数据源，Bearer token）
- api.py:         数据访问封装层（Pandascore + TTL 缓存 + Result 封装）
- bilibili.py / bilibili_dynamic.py / weibo.py: 第三方平台数据抓取
"""

from . import api, bilibili, bilibili_dynamic, pandascore, weibo
from .api import (
    close_session,
    get_all_leagues,
    get_all_teams,
    get_champion,
    get_champions,
    get_game_detail,
    get_game_events,
    get_game_frames,
    get_item,
    get_items,
    get_live_matches,
    get_masteries,
    get_match_detail,
    get_match_games,
    get_match_players_stats,
    get_match_result,
    get_player,
    get_player_stats,
    get_players,
    get_rune,
    get_rune_path,
    get_rune_paths,
    get_runes,
    get_schedule,
    get_series,
    get_series_detail,
    get_series_teams,
    get_spell,
    get_spells,
    get_standings,
    get_team_stats,
    get_today_schedule,
    get_tournament,
    get_tournament_teams_stats,
    get_tournaments,
    get_upcoming_schedule,
)
from .bilibili import (
    fetch_bilibili_comments,
    fetch_bilibili_dynamics,
    fetch_bilibili_live_status,
    fetch_bilibili_replays,
    fetch_bilibili_reply_replies,
    fetch_bilibili_updates,
)
from .bilibili_dynamic import fetch_blg_bp_dynamics
from .weibo import fetch_weibo_announcements, fetch_weibo_by_keyword, fetch_weibo_posters

__all__ = [
    # === api.py（对外数据接口）===
    "close_session",
    "get_schedule",
    "get_today_schedule",
    "get_upcoming_schedule",
    "get_live_matches",
    "get_match_result",
    "get_match_detail",
    "get_standings",
    "get_all_leagues",
    "get_all_teams",
    "get_game_detail",
    "get_game_events",
    "get_game_frames",
    "get_match_games",
    "get_match_players_stats",
    "get_team_stats",
    "get_tournament_teams_stats",
    # === reference data ===
    "get_champions",
    "get_champion",
    "get_items",
    "get_item",
    "get_spells",
    "get_spell",
    "get_runes",
    "get_rune",
    "get_rune_paths",
    "get_rune_path",
    "get_masteries",
    # === players ===
    "get_players",
    "get_player",
    "get_player_stats",
    # === series / tournaments ===
    "get_series",
    "get_series_detail",
    "get_series_teams",
    "get_tournaments",
    "get_tournament",
    # === bilibili ===
    "fetch_bilibili_updates",
    "fetch_bilibili_dynamics",
    "fetch_bilibili_live_status",
    "fetch_bilibili_replays",
    "fetch_bilibili_comments",
    "fetch_bilibili_reply_replies",
    # === bilibili_dynamic ===
    "fetch_blg_bp_dynamics",
    # === weibo ===
    "fetch_weibo_by_keyword",
    "fetch_weibo_posters",
    "fetch_weibo_announcements",
]