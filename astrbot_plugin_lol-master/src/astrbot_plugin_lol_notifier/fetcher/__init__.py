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
from .weibo import fetch_weibo_announcements, fetch_weibo_by_keyword, fetch_weibo_posters

__all__ = [
    # 赛事 API
    "close_session",
    "get_schedule",
    "get_match_result",
    "get_match_bp",
    "get_match_detail",
    "get_standings",
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
