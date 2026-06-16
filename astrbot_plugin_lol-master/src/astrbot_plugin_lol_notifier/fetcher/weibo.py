"""Weibo content fetcher for LoL notifications.

Supports:
- 定时监控多个微博账号 (URL/UID/用户名)
- 精准推送最新更新，自动过滤置顶微博
- Cookie 配置确保稳定性
- 屏蔽词过滤 + 白名单关键词过滤
- 原创/转发微博选择推送
- 数据持久化避免重复推送
"""

from __future__ import annotations


# 微博官方账号配置
LOL_OFFICIAL_WEIBO_UIDS = [
    "6537214902",  # 英雄联盟赛事
    # 可以添加更多官方账号
]


async def fetch_weibo_posters() -> list[dict]:
    """Fetch match posters and event graphics from official Weibo accounts.
    
    Returns:
        List of posters with keys: id, text, images, url, created_at, is_top
    """
    # TODO: 接入微博官方账号内容抓取
    # 需要配置微博 Cookie 才能稳定抓取
    # 过滤置顶微博，只推送最新内容
    return []


async def fetch_weibo_announcements() -> list[dict]:
    """Fetch official announcements and pre-match posters from Weibo.
    
    Returns:
        List of announcements with keys: id, text, images, url, created_at, is_original
    """
    # TODO: 抓取微博赛前官宣、阵容和海报内容
    # 支持屏蔽词过滤
    # 支持白名单关键词过滤（如 "赛程"、"对阵"、"首发"）
    return []


async def fetch_weibo_by_keyword(keyword: str, filter_repost: bool = True) -> list[dict]:
    """Fetch Weibo posts by keyword.
    
    Args:
        keyword: 搜索关键词
        filter_repost: 是否过滤转发微博，只保留原创
    
    Returns:
        List of posts matching the keyword
    """
    # TODO: 根据关键词搜索微博内容
    # 支持自定义消息格式
    return []
