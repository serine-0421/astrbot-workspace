"""LoL plugin fetcher package."""

from .api import (
    close_session,
    get_match_bp,
    get_match_detail,
    get_match_result,
    get_schedule,
    get_standings,
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
    fetch_live_frame,
    fetch_live_match_details,
    fetch_live_matches,
    fetch_match_detail as lolesports_fetch_match_detail,
    fetch_schedule as lolesports_fetch_schedule,
    fetch_standings as lolesports_fetch_standings,
    get_api_key as lolesports_get_api_key,
    set_api_key as lolesports_set_api_key,
)
from .weibo import fetch_weibo_announcements, fetch_weibo_by_keyword, fetch_weibo_posters

__all__ = [
    # 赛事 API（封装层）
    "close_session",
    "get_schedule",
    "get_match_result",
    "get_match_bp",
    "get_match_detail",
    "get_standings",
    # API Key 管理
    "lolesports_get_api_key",
    "lolesports_set_api_key",
    # LoL Esports 原始抓取函数
    "lolesports_close_session",
    "lolesports_fetch_schedule",
    "lolesports_fetch_standings",
    "lolesports_fetch_match_detail",
    "fetch_live_matches",
    "fetch_live_match_details",
    "fetch_live_frame",
    # B站 LOL 官号视频
    "fetch_bilibili_updates",
    "fetch_bilibili_replays",
    "fetch_bilibili_live_status",
    "fetch_bilibili_comments",
    "fetch_bilibili_reply_replies",
    # B站 BLG BP 动态
    "fetch_blg_bp_dynamics",
    # 微博海报
    "fetch_weibo_posters",
    "fetch_weibo_announcements",
    "fetch_weibo_by_keyword",
]
