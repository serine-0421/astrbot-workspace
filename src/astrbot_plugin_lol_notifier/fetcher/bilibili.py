"""Bilibili content fetcher for LoL notifications.

Supports monitoring:
- 📺 Video updates from official UP主

风控说明:
  B站对无 Cookie 的请求会触发 -352 风控。
  配置 bilibili_cookie 可绕过风控（从浏览器 F12 → Application → Cookies 复制）。
  也可设置环境变量 BILIBILI_COOKIE。
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import time as time_mod
from typing import Any
from urllib.parse import urlencode

import httpx

from astrbot.api import logger

# Bilibili 官方账号 UID
LOL_OFFICIAL_UID = "50329118"

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

# WBI 混淆表
_MIXIN_ENC = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52,
]

# WBI keys 缓存
_wbi_cache: tuple[str, str, float] | None = None

# B站 Cookie（运行时设置）
_bilibili_cookie: str = ""


def set_bilibili_cookie(cookie: str) -> None:
    """设置 B站 Cookie（由调度器在初始化时调用）。"""
    global _bilibili_cookie
    _bilibili_cookie = (cookie or "").strip()
    if _bilibili_cookie:
        logger.info("[Bilibili] Cookie configured (length=%d)", len(_bilibili_cookie))


def _get_cookie_header() -> str:
    """获取当前 Cookie 字符串。"""
    if _bilibili_cookie:
        return _bilibili_cookie
    return os.environ.get("BILIBILI_COOKIE", "")


def _build_headers(referer: str = "https://www.bilibili.com") -> dict[str, str]:
    """构建带 Cookie 和 Origin 的请求头（绕过风控）。"""
    headers = {
        "User-Agent": _USER_AGENT,
        "Referer": referer,
        "Origin": "https://www.bilibili.com",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    cookie = _get_cookie_header()
    if cookie:
        headers["Cookie"] = cookie
    return headers


async def fetch_bilibili_updates() -> list[dict[str, Any]]:
    """获取 B 站官方账号的最新视频投稿

    优先尝试公开 API，被限频后切换到 WBI 签名接口。

    Returns:
        [{"type":"video","bvid":"BV...","title":"...","description":"...",
          "pubdate":1234567890,"url":"https://...","cover":"https://..."}]
    """
    # 方案 1: 公开接口（通常够用，不需要 Cookie）
    result = await _fetch_public()
    if result:
        return result

    # 方案 2: WBI 签名接口（绕过限频）
    result = await _fetch_wbi()
    if result:
        return result

    logger.warning("[Bilibili] All fetch methods failed, returning empty")
    return []


# ──────────────── 方案 1: 公开 API ────────────────

async def _fetch_public() -> list[dict[str, Any]]:
    """公开 space/arc/search 接口（无需签名）"""
    try:
        url = "https://api.bilibili.com/x/space/arc/search"
        params = {"mid": LOL_OFFICIAL_UID, "ps": 10, "pn": 1}
        headers = _build_headers(f"https://space.bilibili.com/{LOL_OFFICIAL_UID}")

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params, headers=headers)
            data = resp.json()
            code = data.get("code")

            if code == 0:
                return _parse_vlist(data)
            elif code == -352:
                logger.warning(
                    "[Bilibili] ⚠️ 风控拦截 (-352): 未配置 Cookie 或 Cookie 已失效。"
                    "请在插件配置中填写 bilibili_cookie"
                )
            elif code == -799:
                logger.debug("[Bilibili] Public API rate-limited (-799)")
            else:
                logger.debug(f"[Bilibili] Public API error {code}: {data.get('message')}")

    except Exception as e:
        logger.debug(f"[Bilibili] Public API exception: {e}")

    return []


# ──────────────── 方案 2: WBI 签名 API ────────────────

async def _fetch_wbi() -> list[dict[str, Any]]:
    """WBI 签名接口（空间投稿搜索）"""
    try:
        img_key, sub_key = await _get_wbi_keys()
        if not img_key or not sub_key:
            logger.warning("[Bilibili] 无法获取 WBI 密钥（nav 端点被风控），跳过 WBI")
            return []

        mixin_key = "".join((img_key + sub_key)[i] for i in _MIXIN_ENC)[:32]

        params = {
            "mid": LOL_OFFICIAL_UID,
            "ps": 10, "tid": 0, "pn": 1,
            "order": "pubdate", "keyword": "",
        }
        params["wts"] = round(time_mod.time())
        params = dict(sorted(params.items()))
        query = urlencode(params)
        params["w_rid"] = hashlib.md5((query + mixin_key).encode()).hexdigest()

        headers = _build_headers(f"https://space.bilibili.com/{LOL_OFFICIAL_UID}/video")

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://api.bilibili.com/x/space/wbi/arc/search",
                params=params,
                headers=headers,
            )
            data = resp.json()
            code = data.get("code")

            if code == 0:
                return _parse_vlist(data)
            elif code == -352:
                logger.warning("[Bilibili] WBI API 风控 (-352): Cookie 无效或缺失")
            else:
                logger.debug(f"[Bilibili] WBI API error {code}: {data.get('message')}")

    except Exception as e:
        logger.debug(f"[Bilibili] WBI API exception: {e}")

    return []


async def _get_wbi_keys() -> tuple[str, str]:
    """获取 WBI 签名密钥对（30 分钟缓存）。

    如果 nav 端点被风控（-352），返回空字符串，调用方应跳过 WBI 请求。
    """
    global _wbi_cache
    now = time_mod.time()

    if _wbi_cache and (now - _wbi_cache[2]) < 1800:
        return _wbi_cache[0], _wbi_cache[1]

    try:
        headers = _build_headers("https://www.bilibili.com")
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://api.bilibili.com/x/web-interface/nav",
                headers=headers,
            )
            data = resp.json()
            code = data.get("code")

            if code == -352:
                logger.warning(
                    "[Bilibili] ⚠️ nav 端点风控 (-352)，无法获取 WBI 密钥。"
                    "请配置 bilibili_cookie 后重试。"
                )
                _wbi_cache = ("", "", now)
                return "", ""

            if code != 0 or "data" not in data:
                logger.debug(f"[Bilibili] nav API error {code}: {data.get('message')}")
                _wbi_cache = ("", "", now)
                return "", ""

            wbi = data["data"].get("wbi_img", {})
            if not wbi:
                logger.debug("[Bilibili] nav API 未返回 wbi_img")
                _wbi_cache = ("", "", now)
                return "", ""

            img_key = wbi["img_url"].rsplit("/", 1)[1].split(".")[0]
            sub_key = wbi["sub_url"].rsplit("/", 1)[1].split(".")[0]

        _wbi_cache = (img_key, sub_key, now)
        return img_key, sub_key

    except Exception as e:
        logger.debug(f"[Bilibili] nav API exception: {e}")
        _wbi_cache = ("", "", now)
        return "", ""


# ──────────────── 公共解析 ────────────────

def _parse_vlist(data: dict) -> list[dict[str, Any]]:
    """解析 API 返回的 vlist → 标准格式"""
    vlist = data.get("data", {}).get("list", {}).get("vlist", [])
    results: list[dict[str, Any]] = []

    for video in vlist:
        bvid = video.get("bvid", "")
        results.append({
            "type": "video",
            "bvid": bvid,
            "title": video.get("title", ""),
            "description": video.get("description", ""),
            "pubdate": video.get("created", 0),
            "url": f"https://www.bilibili.com/video/{bvid}",
            "cover": video.get("pic", ""),
        })

    return results


async def fetch_bilibili_replays() -> list[dict]:
    """Fetch official replay videos (keyword filtering)."""
    # TODO: 从 fetch_bilibili_updates 结果中筛选标题包含"回放"等关键词
    return []


async def fetch_bilibili_live_status() -> list[dict]:
    """Fetch live streaming status."""
    # TODO: 实现直播状态监控
    return []


async def fetch_bilibili_comments() -> list[dict]:
    """Fetch UP主在评论区的发言."""
    # TODO: 实现评论区监控
    return []


async def fetch_bilibili_reply_replies() -> list[dict]:
    """Fetch UP主在楼中楼的回复."""
    # TODO: 实现楼中楼监控
    return []
