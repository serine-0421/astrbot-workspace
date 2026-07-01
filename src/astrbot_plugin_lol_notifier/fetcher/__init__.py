"""LoL plugin fetcher package — 数据抓取层.

架构:
- pandascore.py:  Pandascore HTTP 客户端（主数据源，Bearer token）
- lolesports.py:  citoapi HTTP 客户端（备用数据源，x-api-key）
- api.py:         数据访问封装层（Pandascore 优先 + citoapi 回退 + TTL 缓存 + Result 封装）
- bilibili.py / bilibili_dynamic.py / weibo.py: 第三方平台数据抓取
"""

from . import api, bilibili, bilibili_dynamic, lolesports, pandascore, weibo
from .api import (
    close_session,
    get_all_leagues,
    get_all_teams,
    get_game_detail,
    get_live_matches,
    get_match_detail,
    get_match_result,
    get_schedule,
    get_standings,
    get_today_schedule,
    get_upcoming_schedule,
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
    # === lolesports.py（citoapi 底层）===
    "lolesports_close_session",
    "lolesports_get_api_key",
    "lolesports_set_api_key",
    # === bilibili ===
    "fetch_bilibili_updates",
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