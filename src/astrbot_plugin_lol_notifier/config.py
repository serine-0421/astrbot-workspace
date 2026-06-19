"""Plugin configuration helpers for LoL notifier."""

from __future__ import annotations

from typing import Any

DEFAULT_CONFIG: dict[str, Any] = {
    "follow_teams": [],
    "enable_image_render": False,
    "enable_match_notifications": True,
    # ── Riot 开发者 API（赛程/排名/比赛详情） ──
    # API Key 优先级: 环境变量 RIOT_API_KEY > 此处的 riot_api_key > 自动刷新
    "riot_api_key": "",
    # Riot 账号（用于自动刷新 Key，每 24h 自动登录获取新 Key）
    "riot_username": "",
    "riot_password": "",
    # ── B站: 英雄联盟赛事官方号（视频推送） ──
    "bilibili_uid": "50329118",
    "enable_bilibili_video_push": True,
    "bilibili_check_interval": 60,
    "bilibili_cookie": "",
    # ── B站: BLG 电子竞技俱乐部（BP 图文推送） ──
    "bilibili_blg_uid": "545271146",
    "enable_bilibili_blg_bp_push": True,
    # ── 微博: 各队官号（海报推送） ──
    "weibo_uids": [
        "6537214902",  # 英雄联盟赛事
    ],
    "weibo_cookie": "",
    "weibo_check_interval": 300,
    "enable_weibo_poster_push": True,
    # ── 保守字段（保留兼容） ──
    "enable_bilibili_updates": True,
    "enable_weibo_updates": True,
    "enable_bilibili_live": False,
    "enable_bilibili_comments": False,
    "weibo_filter_repost": False,
    "weibo_blacklist": [],
    "weibo_whitelist": [],
}


# ── B站 LOL 官号 ──

def get_bilibili_uid(config: Any) -> str:
    return str(config.get("bilibili_uid", DEFAULT_CONFIG["bilibili_uid"])) if config else DEFAULT_CONFIG["bilibili_uid"]


def is_bilibili_video_push_enabled(config: Any) -> bool:
    return bool(config.get("enable_bilibili_video_push", True)) if config else True


def get_bilibili_cookie(config: Any) -> str:
    """获取 B站 Cookie，用于绕过风控。环境变量 BILIBILI_COOKIE 优先。"""
    import os
    env_cookie = os.environ.get("BILIBILI_COOKIE", "")
    if env_cookie:
        return env_cookie
    return str(config.get("bilibili_cookie", "")) if config else ""


# ── B站 BLG ──

def get_blg_uid(config: Any) -> str:
    return str(config.get("bilibili_blg_uid", DEFAULT_CONFIG["bilibili_blg_uid"])) if config else DEFAULT_CONFIG["bilibili_blg_uid"]


def is_blg_bp_push_enabled(config: Any) -> bool:
    return bool(config.get("enable_bilibili_blg_bp_push", True)) if config else True


# ── 微博 ──

def get_weibo_uids(config: Any) -> list[str]:
    return list(config.get("weibo_uids", DEFAULT_CONFIG["weibo_uids"])) if config else DEFAULT_CONFIG["weibo_uids"]


def is_weibo_poster_push_enabled(config: Any) -> bool:
    return bool(config.get("enable_weibo_poster_push", True)) if config else True


# ── 通用 ──

def get_followed_teams(config: Any) -> list[str]:
    return list(config.get("follow_teams", [])) if config else []


def is_image_mode_enabled(config: Any) -> bool:
    return bool(config.get("enable_image_render", False)) if config else False


# 向后兼容别名
is_bilibili_updates_enabled = is_bilibili_video_push_enabled
is_weibo_updates_enabled = is_weibo_poster_push_enabled
