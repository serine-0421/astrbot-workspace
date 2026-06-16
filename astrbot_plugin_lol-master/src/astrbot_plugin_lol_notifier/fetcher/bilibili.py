"""Bilibili content fetcher for LoL notifications.

Supports monitoring:
- 📺 Video/图文/文字/转发/专栏动态 (feed/space with WBI signature)
- 🔴 Live status (开播/下播 + 直播时长)
- 💬 UP主在自己动态/视频评论区的发言 (reply/main)
- 💬💬 UP主在楼中楼里回复粉丝 (reply/reply)
- 🖼️ 转发动态附带的原动态图片解析
- 🖼️ UP主评论/楼中楼回复里的图片解析
"""

from __future__ import annotations


# Bilibili 官方账号 UID 配置
LOL_OFFICIAL_UIDS = [
    "401742377",  # 哔哩哔哩英雄联盟赛事
    # 可以添加更多官方账号
]


async def fetch_bilibili_updates() -> list[dict]:
    """Fetch the latest updates from Bilibili official LoL channels.
    
    Returns:
        List of updates with keys: id, type, title, description, url, images, timestamp
    """
    # TODO: 接入哔哩哔哩英雄联盟赛事账号 API
    # 1. 视频投稿: GET https://api.bilibili.com/x/space/wbi/arc/search
    # 2. 动态: GET https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space
    # 3. 专栏: GET https://api.bilibili.com/x/space/article
    # 需要实现 WBI 签名绕过 -412 错误
    return []


async def fetch_bilibili_replays() -> list[dict]:
    """Fetch official replay videos and announcements from Bilibili.
    
    Returns:
        List of replay videos with keys: bvid, title, url, cover, duration, pubdate
    """
    # TODO: 从 B 站官号抓取最新回放视频、赛后采访与官方直播动态
    # 过滤标题包含 "回放"、"精彩"、"高光" 等关键词
    return []


async def fetch_bilibili_live_status() -> list[dict]:
    """Fetch live streaming status of official channels.
    
    Returns:
        List of live status with keys: uid, room_id, live_status, title, live_time
    """
    # TODO: GET https://api.live.bilibili.com/room/v1/Room/get_status_info_by_uids
    return []


async def fetch_bilibili_comments() -> list[dict]:
    """Fetch UP主在动态/视频评论区的发言.
    
    Returns:
        List of comments with keys: rpid, oid, message, ctime, pictures
    """
    # TODO: GET https://api.bilibili.com/x/v2/reply/main
    # 支持热度和时间双模式排序
    return []


async def fetch_bilibili_reply_replies() -> list[dict]:
    """Fetch UP主在楼中楼里的回复.
    
    Returns:
        List of replies with keys: rpid, root, message, ctime, pictures
    """
    # TODO: GET https://api.bilibili.com/x/v2/reply/reply
    # 需要翻页获取所有楼中楼回复
    return []
