"""Weibo 内容抓取器 — LPL 赛前海报推送。

流程：检测英雄联盟赛事微博更新 → 关键词匹配 "LPL" + "预告" → 下载图片 → 推送。
使用 m.weibo.cn 移动端 API，无需 Cookie 即可访问公开内容。
"""

from __future__ import annotations

import asyncio
import os
import re
from typing import Any

import httpx

from astrbot.api import logger

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

# HTML 标签清洗
_TAG_RE = re.compile(r"<[^>]+>")

# 微博 Cookie（硬编码，也可通过环境变量 WEIBO_COOKIE 覆盖）
_DEFAULT_COOKIE: str = (
    "SCF=An5YsYLqRu2u-fMQVGzzeVbXKqhJ2bMpLzY9S1xsOkSXYkLQapAdAr_lh_yhef5QuhIdy1jg7z3urXrzjEBzJaA.; "
    "SINAGLOBAL=4360766153826.32.1781671800393; "
    "ULV=1781671800395:1:1:1:4360766153826.32.1781671800393:; "
    "PC_TOKEN=d004faf008; "
    "ALF=1785664495; "
    "SUB=_2A25HQ_a_DeRhGeFG41EQ9y3JzT6IHXVkIXZ3rDV8PUJbkNAbLW2tkW1NeKOkVyk-mqXRLKOKAo87jvY-AoqbVO3Q; "
    "SUBP=0033WrSXqPxfM725Ws9jqgMF55529P9D9W5RpnkEqeHiHppAJIvC7Rv-5JpX5KMhUgL.FoMR1hepS0efSoz2dJLoI7y8THSLMJLV9Btt; "
    "XSRF-TOKEN=PDlIuvM6VvTOYPBGV7iTyXZH; "
    "WBPSESS=49UgBhdQBFvCtcmuaB4XIXbtzcb4li8EDkPQdndhuSb_hiUoH4y7K4mNQUMO5UosJfZGoAya0nT3y5KAl-j5NEvJ_EQvadYgRW-ILfml_U_nDHZ5t4SFm4M1ChOdqQYa3lrqZkw7lq75CSydHSuFyA=="
)
_WEIBO_COOKIE: str = _DEFAULT_COOKIE or os.environ.get("WEIBO_COOKIE", "")


def set_weibo_cookie(cookie: str) -> None:
    """设置微博 Cookie（一般无需手动调用，模块初始化时已自动加载）。"""
    global _WEIBO_COOKIE
    _WEIBO_COOKIE = (cookie or _DEFAULT_COOKIE or os.environ.get("WEIBO_COOKIE", "")).strip()
    if _WEIBO_COOKIE:
        logger.info("[Weibo] Cookie configured (length=%d)", len(_WEIBO_COOKIE))


def _get_cookie_header() -> str:
    """获取当前 Cookie 字符串。"""
    if _WEIBO_COOKIE:
        return _WEIBO_COOKIE
    return os.environ.get("WEIBO_COOKIE", "")


def _build_headers(referer: str = "https://m.weibo.cn") -> dict[str, str]:
    """构建带 Cookie 和 Referer 的请求头。"""
    headers = {
        "User-Agent": _USER_AGENT,
        "Referer": referer,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    cookie = _get_cookie_header()
    if cookie:
        headers["Cookie"] = cookie
    return headers


def _strip_html(text: str) -> str:
    """去除 HTML 标签，保留纯文本。"""
    return _TAG_RE.sub("", text).strip()


def _extract_images(post_data: dict) -> list[str]:
    """从帖子数据中提取图片 URL 列表（优先原图）。"""
    images: list[str] = []
    pics = post_data.get("pics", [])
    if not pics:
        # mblog 嵌套结构
        mblog = post_data.get("mblog", {})
        pics = mblog.get("pics", [])
    for pic in pics:
        url = pic.get("large", {}).get("url") or pic.get("url", "")
        if url:
            images.append(url)
    return images


async def _fetch_user_posts(uid: str) -> list[dict[str, Any]]:
    """获取指定微博用户的最新帖子。"""
    container_id = f"107603{uid}"
    url = "https://m.weibo.cn/api/container/getIndex"
    params = {"type": "uid", "value": uid, "containerid": container_id}
    headers = _build_headers(f"https://m.weibo.cn/u/{uid}")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params, headers=headers)
            data = resp.json()

        if data.get("ok") != 1:
            logger.debug(f"[Weibo] API error for uid={uid}: {data.get('msg', 'unknown')}")
            return []

        cards = data.get("data", {}).get("cards", [])
        posts: list[dict[str, Any]] = []

        for card in cards:
            if card.get("card_type") != 9:
                continue
            mblog = card.get("mblog", {})
            if not mblog:
                continue

            text_raw = mblog.get("text", "")
            text_clean = _strip_html(text_raw)

            posts.append({
                "id": str(mblog.get("id", "")),
                "mid": str(mblog.get("mid", mblog.get("id", ""))),
                "text": text_clean,
                "text_raw": text_raw,
                "images": _extract_images(mblog),
                "url": f"https://weibo.com/{uid}/{mblog.get('mid', '')}",
                "created_at": mblog.get("created_at", ""),
                "uid": uid,
                "user_name": mblog.get("user", {}).get("screen_name", ""),
            })

        return posts

    except Exception as e:
        logger.debug(f"[Weibo] Exception for uid={uid}: {e}")
        return []


def _is_poster(post: dict) -> bool:
    """判断是否为赛前海报：同时包含"LPL"和"预告"关键词。"""
    text = post.get("text", "")
    return ("LPL" in text) and ("预告" in text)


async def fetch_weibo_posters(uids: list[str] | None = None) -> list[dict[str, Any]]:
    """获取英雄联盟赛事微博 (UID 6537214902) 中匹配"LPL+预告"的赛前海报。

    Args:
        uids: 微博 UID 列表，None 时不抓取。

    Returns:
        [{"id":"...","mid":"...","text":"...","images":[...],"url":"...","uid":"..."}]
    """
    if not uids:
        return []

    all_posts: list[dict[str, Any]] = []

    for uid in uids:
        posts = await _fetch_user_posts(uid)
        for post in posts:
            if _is_poster(post):
                all_posts.append(post)

    if all_posts:
        logger.info(f"[Weibo] Found {len(all_posts)} poster(s) across {len(uids)} account(s)")

    return all_posts


# ── 保留兼容旧接口的占位函数 ──

async def fetch_weibo_announcements() -> list[dict]:
    """Deprecated: 使用 fetch_weibo_posters 替代。"""
    return []


async def fetch_weibo_by_keyword(keyword: str, filter_repost: bool = True) -> list[dict]:
    """Deprecated: 暂未实现关键词搜索。"""
    return []

