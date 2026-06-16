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
from .weibo import fetch_weibo_announcements, fetch_weibo_by_keyword, fetch_weibo_posters

__all__ = [
    "close_session",
    "get_schedule",
    "get_match_result",
    "get_match_bp",
    "get_match_detail",
    "get_standings",
    "fetch_bilibili_updates",
    "fetch_bilibili_replays",
    "fetch_bilibili_live_status",
    "fetch_bilibili_comments",
    "fetch_bilibili_reply_replies",
    "fetch_weibo_announcements",
    "fetch_weibo_posters",
    "fetch_weibo_by_keyword",
]
