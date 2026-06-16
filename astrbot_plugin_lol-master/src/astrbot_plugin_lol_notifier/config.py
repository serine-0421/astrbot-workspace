"""Plugin configuration helpers for LoL notifier."""

from __future__ import annotations

from typing import Any

DEFAULT_CONFIG = {
    "follow_teams": [],
    "enable_image_render": False,
    "enable_match_notifications": True,
    "enable_bilibili_updates": True,
    "enable_weibo_updates": True,
    # B站配置
    "bilibili_uids": ["401742377"],  # 哔哩哔哩英雄联盟赛事账号 UID
    "bilibili_check_interval": 60,   # 检查间隔（秒）
    "enable_bilibili_live": True,    # 是否监控直播状态
    "enable_bilibili_comments": False,  # 是否监控评论区
    # 微博配置
    "weibo_uids": [],                # 监控的微博 UID 列表
    "weibo_cookie": "",              # 微博 Cookie，必填以避免被封
    "weibo_check_interval": 300,     # 检查间隔（秒），建议不低于 5 分钟
    "weibo_filter_repost": False,    # 是否过滤转发微博
    "weibo_blacklist": [],           # 屏蔽词列表
    "weibo_whitelist": [],           # 白名单关键词（为空则推全部）
}


def get_followed_teams(config: Any) -> list[str]:
    return list(config.get("follow_teams", [])) if config else []


def is_image_mode_enabled(config: Any) -> bool:
    return bool(config.get("enable_image_render", False)) if config else False


def get_bilibili_uids(config: Any) -> list[str]:
    return list(config.get("bilibili_uids", DEFAULT_CONFIG["bilibili_uids"])) if config else DEFAULT_CONFIG["bilibili_uids"]


def get_weibo_uids(config: Any) -> list[str]:
    return list(config.get("weibo_uids", [])) if config else []


def is_bilibili_updates_enabled(config: Any) -> bool:
    return bool(config.get("enable_bilibili_updates", True)) if config else True


def is_weibo_updates_enabled(config: Any) -> bool:
    return bool(config.get("enable_weibo_updates", True)) if config else True
