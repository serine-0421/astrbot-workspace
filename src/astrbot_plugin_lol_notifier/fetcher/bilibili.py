"""Bilibili content fetcher — unified multi-account.

Supports per-UID:
- 📺 Video updates   (space/arc/search + WBI)
- 📰 Article dynamics (polymer web-dynamic feed)
- 🔴 Live status     (stub, not yet implemented)

风控说明:
  B站对无 Cookie 的请求会触发 -352 风控。
  Cookie 通过 _DEFAULT_COOKIE 常量或环境变量 BILIBILI_COOKIE 注入。
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import random
import time as time_mod
from typing import Any
from urllib.parse import urlencode

import httpx

from astrbot.api import logger

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

# WBI 缓存 TTL（秒）
_WBI_CACHE_TTL: float = 1800.0       # 成功时缓存 30 分钟
_WBI_NAV_RETRY_DELAY: float = 2.0    # nav 端点重试前等待
_WBI_NAV_MAX_RETRIES: int = 1        # nav 端点额外重试次数

# 请求间最小间隔（秒），避免同一 UID 连续请求触发风控
_MIN_REQUEST_GAP: float = 1.5

# B站 Cookie（硬编码，也可通过环境变量 BILIBILI_COOKIE 覆盖）
_DEFAULT_COOKIE: str = (
    "buvid3=E8A25E15-F6A9-7B35-078E-FBDC9D92E5C579886infoc; "
    "b_nut=1780047979; "
    "_uuid=E15B659A-AE97-D52A-810103-A10B526DF9C6778210infoc; "
    "buvid_fp=d4a60f9b5ae81fdb74e283e8891b0026; "
    "buvid4=7EF8EA8B-65AC-50FE-EFC4-4E90EE26F2F780555-026052917-qsiivOz/4B9KKEExDhYE0Q%3D%3D; "
    "DedeUserID=1078666620; "
    "DedeUserID__ckMd5=365dbaf44efc77ac; "
    "theme-tip-show=SHOWED; "
    "theme-avatar-tip-show=SHOWED; "
    "CURRENT_QUALITY=0; "
    "rpdid=|(umYmmll)J~0J'u~)||lukJ~; "
    "theme-switch-show=SHOWED; "
    "SESSDATA=b2e127f7%2C1798864035%2Cfbad1%2A71CjBJsjKMwwV6eHqKgyzYuNyO1istnboKlwZDNXLBrX77JYW2vBNF0krAVoDPIUKT5DwSVkx2dDQxamVoR19BYTQwcVBxUlZtTGRlVzdUdGVHbWstcHJUc1hzY1E4RHZ2U2dMSmRfM2hXa0NSTHU4ZFJkcjBlMXEwbG1IM09EQTFyTzl4M3YwcXpBIIEC; "
    "bili_jct=4a35cd6e34b846a5044afbda8c578a82; "
    "sid=8spkzuhr; "
    "bmg_af_switch=1; "
    "bmg_src_def_domain=i2.hdslb.com; "
    "bmg_af_sc={\"none\":{\"on\":1,\"def\":\"i2.hdslb.com\"},\"sgp\":{\"on\":1,\"def\":\"i2-sgp.hdslb.com\"}}; "
    "bili_ticket=eyJhbGciOiJIUzI1NiIsImtpZCI6InMwMyIsInR5cCI6IkpXVCJ9."
    "eyJleHAiOjE3ODM3NTYzMDIsImlhdCI6MTc4MzQ5NzA0MiwicGx0IjotMX0."
    "Ky2Gc2UQsSOJmmpZS7mLpg5Gqo1YU1Ex1BY0U-oOWLQ; "
    "bili_ticket_expires=1783756242; "
    "PVID=5; "
    "CURRENT_FNVAL=4048; "
    "bp_t_offset_1078666620=1222615015501070336; "
    "home_feed_column=4; "
    "browser_resolution=1357-956; "
    "b_lsid=2CA7A464_19F44EE2DF8; "
    "b_lsid=BE586282_19F17EACF7F"
)
_bilibili_cookie: str = _DEFAULT_COOKIE or os.environ.get("BILIBILI_COOKIE", "")


def set_bilibili_cookie(cookie: str) -> None:
    """设置 B站 Cookie（一般无需手动调用，模块初始化时已自动加载）。"""
    global _bilibili_cookie
    _bilibili_cookie = (cookie or _DEFAULT_COOKIE or os.environ.get("BILIBILI_COOKIE", "")).strip()
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


# ═══════════════════════════════════════════════════
#  视频
# ═══════════════════════════════════════════════════

async def fetch_bilibili_updates(uid: str = "50329118") -> list[dict[str, Any]]:
    """获取指定 UID 的最新视频投稿。

    优先尝试公开 API，被限频后延迟再切换到 WBI 签名接口。

    Returns:
        [{"type":"video","bvid":"BV...","title":"...","description":"...",
          "pubdate":1234567890,"url":"https://...","cover":"https://..."}]
    """
    result = await _fetch_public(uid)
    if result:
        return result

    # 公开 API 失败后加延迟，避免紧随请求触发风控
    await asyncio.sleep(_MIN_REQUEST_GAP)

    result = await _fetch_wbi(uid)
    if result:
        return result

    logger.warning(f"[Bilibili:{uid}] All fetch methods failed, returning empty")
    return []


async def _fetch_public(uid: str) -> list[dict[str, Any]]:
    """公开 space/arc/search 接口（无需签名）"""
    try:
        url = "https://api.bilibili.com/x/space/arc/search"
        params = {"mid": uid, "ps": 10, "pn": 1}
        headers = _build_headers(f"https://space.bilibili.com/{uid}")

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params, headers=headers)
            data = resp.json()
            code = data.get("code")

            if code == 0:
                return _parse_vlist(data)
            elif code == -352:
                logger.warning(
                    f"[Bilibili:{uid}] ⚠️ 风控拦截 (-352): Cookie 无效或缺失"
                )
            elif code == -799:
                logger.debug(f"[Bilibili:{uid}] Public API rate-limited (-799)")
            else:
                logger.debug(f"[Bilibili:{uid}] Public API error {code}: {data.get('message')}")

    except Exception as e:
        logger.debug(f"[Bilibili:{uid}] Public API exception: {e}")

    return []


async def _fetch_wbi(uid: str) -> list[dict[str, Any]]:
    """WBI 签名接口（空间投稿搜索）"""
    try:
        img_key, sub_key = await _get_wbi_keys()
        if not img_key or not sub_key:
            logger.warning("[Bilibili] 无法获取 WBI 密钥（nav 端点被风控），跳过 WBI")
            return []

        mixin_key = "".join((img_key + sub_key)[i] for i in _MIXIN_ENC)[:32]

        params = {
            "mid": uid,
            "ps": 10, "tid": 0, "pn": 1,
            "order": "pubdate", "keyword": "",
        }
        params["wts"] = round(time_mod.time())
        params = dict(sorted(params.items()))
        query = urlencode(params)
        params["w_rid"] = hashlib.md5((query + mixin_key).encode()).hexdigest()

        headers = _build_headers(f"https://space.bilibili.com/{uid}/video")

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
                logger.warning(f"[Bilibili:{uid}] WBI API 风控 (-352): Cookie 无效或缺失")
            else:
                logger.debug(f"[Bilibili:{uid}] WBI API error {code}: {data.get('message')}")

    except Exception as e:
        logger.debug(f"[Bilibili:{uid}] WBI API exception: {e}")

    return []


async def _get_wbi_keys() -> tuple[str, str]:
    """获取 WBI 签名密钥对（成功缓存 30 分钟，失败不缓存以允许其他账号独立重试）。

    如果 nav 端点被风控（-352），返回空字符串，调用方应跳过 WBI 请求。
    失败不做全局缓存，避免一个账号的风控导致其他账号也无法使用 WBI 回退。
    """
    global _wbi_cache
    now = time_mod.time()

    # 仅使用成功缓存（非空密钥且在 TTL 内）
    if _wbi_cache is not None and _wbi_cache[0] and (now - _wbi_cache[2]) < _WBI_CACHE_TTL:
        return _wbi_cache[0], _wbi_cache[1]

    headers = _build_headers("https://www.bilibili.com")

    last_error = ""
    for attempt in range(_WBI_NAV_MAX_RETRIES + 1):
        if attempt > 0:
            await asyncio.sleep(_WBI_NAV_RETRY_DELAY)

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    "https://api.bilibili.com/x/web-interface/nav",
                    headers=headers,
                )
                data = resp.json()
                code = data.get("code")

                if code == -352:
                    last_error = "风控拦截 (-352)"
                    if attempt < _WBI_NAV_MAX_RETRIES:
                        logger.debug(
                            f"[Bilibili] nav 端点 -352，第 {attempt + 1} 次重试..."
                        )
                        continue
                    logger.warning(
                        "[Bilibili] ⚠️ nav 端点风控 (-352)，无法获取 WBI 密钥。"
                        "请配置有效的 bilibili_cookie 后重试。"
                    )
                    return "", ""

                if code != 0 or "data" not in data:
                    last_error = f"API error {code}: {data.get('message')}"
                    if attempt < _WBI_NAV_MAX_RETRIES:
                        logger.debug(f"[Bilibili] nav {last_error}，重试中...")
                        continue
                    logger.debug(f"[Bilibili] nav {last_error}")
                    return "", ""

                wbi = data["data"].get("wbi_img", {})
                if not wbi:
                    logger.debug("[Bilibili] nav API 未返回 wbi_img")
                    return "", ""

                img_key = wbi["img_url"].rsplit("/", 1)[1].split(".")[0]
                sub_key = wbi["sub_url"].rsplit("/", 1)[1].split(".")[0]

            _wbi_cache = (img_key, sub_key, now)
            logger.debug("[Bilibili] WBI keys refreshed successfully")
            return img_key, sub_key

        except Exception as e:
            last_error = str(e)
            if attempt < _WBI_NAV_MAX_RETRIES:
                logger.debug(f"[Bilibili] nav 网络异常，重试: {e}")
                continue
            logger.debug(f"[Bilibili] nav API exception: {e}")

    # 所有重试耗尽 → 不缓存失败，下次调用可独立重试
    logger.warning(f"[Bilibili] nav 端点不可用 ({last_error})，下次调用将重试")
    return "", ""


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


# ═══════════════════════════════════════════════════
#  图文动态
# ═══════════════════════════════════════════════════

async def fetch_bilibili_dynamics(uid: str) -> list[dict[str, Any]]:
    """获取指定 UID 的最新图文动态（polymer web-dynamic feed）。

    返回所有类型的动态，包括图文(DRAW)和视频投稿转发等。
    调用方可按需过滤。

    Returns:
        [{"dynamic_id":"...", "type":"DYNAMIC_TYPE_DRAW",
          "text":"...", "images":[...], "url":"...", "timestamp":1234567890}]
    """
    url = "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space"
    params = {"host_mid": uid, "offset": ""}
    headers = _build_headers(f"https://space.bilibili.com/{uid}/dynamic")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params, headers=headers)
            data = resp.json()

        if data.get("code") != 0:
            code = data.get("code")
            msg = data.get("message", "")
            if code == -352:
                logger.warning(f"[Bilibili:{uid}] 动态 API 风控 (-352): Cookie 无效或缺失")
            else:
                logger.debug(f"[Bilibili:{uid}] Dynamic API error {code}: {msg}")
            return []

        items = data.get("data", {}).get("items", [])
        return _parse_dynamics(items)

    except Exception as e:
        logger.debug(f"[Bilibili:{uid}] Dynamic API exception: {e}")
        return []


def _parse_dynamics(items: list[dict]) -> list[dict[str, Any]]:
    """将 polymer dynamic items 解析为标准格式（含图文和视频转发）。"""
    results: list[dict[str, Any]] = []

    for item in items:
        dyn_type = item.get("type", "")
        modules = item.get("modules", {}).get("module_dynamic", {})
        major = modules.get("major", {})
        desc = modules.get("desc", {})
        author = modules.get("module_author", {})

        text = desc.get("text", "")
        dynamic_id = item.get("id_str", "")
        timestamp = author.get("pub_ts", 0)

        images: list[str] = []
        video_url = ""
        video_title = ""

        if dyn_type == "DYNAMIC_TYPE_DRAW":
            # 图文动态
            draw_items = major.get("draw", {}).get("items", [])
            for img in draw_items:
                src = img.get("src", "")
                if src:
                    images.append(src)

        elif dyn_type == "DYNAMIC_TYPE_AV":
            # 视频投稿转发动态
            archive = major.get("archive", {})
            video_url = archive.get("bvid", "")
            if video_url:
                video_url = f"https://www.bilibili.com/video/{video_url}"
            video_title = archive.get("title", "")
            cover = archive.get("cover", "")
            if cover:
                images.append(cover)

        # 跳过无实质内容的动态
        if not text.strip() and not images and not video_url:
            continue

        results.append({
            "dynamic_id": dynamic_id,
            "type": dyn_type,
            "text": text.strip(),
            "images": images,
            "video_url": video_url,
            "video_title": video_title,
            "url": f"https://t.bilibili.com/{dynamic_id}",
            "timestamp": timestamp,
        })

    return results


async def fetch_bilibili_live_status(uid: str) -> list[dict[str, Any]]:
    """获取指定 UID 的直播间开播状态。

    调用 B站直播间信息 API，返回当前直播标题、人气、封面等。
    未开通直播间或未开播返回空列表。

    Returns:
        [{"room_id":"12345","title":"...","cover":"...","online":1234,
          "url":"https://live.bilibili.com/12345","live_status":1}]
    """
    url = "https://api.live.bilibili.com/room/v1/Room/getRoomInfoOld"
    headers = _build_headers(f"https://space.bilibili.com/{uid}")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params={"mid": uid}, headers=headers)
            data = resp.json()

        if data.get("code") != 0:
            logger.debug(f"[Bilibili:{uid}] Live room API error {data.get('code')}: {data.get('message')}")
            return []

        info = data.get("data", {})
        if not info or info.get("roomStatus") != 1:
            return []

        room_id = str(info.get("roomid", ""))
        cover = info.get("cover", "")
        title = info.get("title", "")
        live_status = info.get("liveStatus", 0)  # 0=offline, 1=live
        online = info.get("online", 0)

        return [{
            "room_id": room_id,
            "title": title,
            "cover": cover,
            "online": online,
            "url": info.get("url", "") or f"https://live.bilibili.com/{room_id}",
            "live_status": live_status,
        }]

    except Exception as e:
        logger.debug(f"[Bilibili:{uid}] Live room API exception: {e}")
        return []


# ═══════════════════════════════════════════════════
#  回放/评论区/楼中楼
# ═══════════════════════════════════════════════════

_REPLAY_KEYWORDS = ["回放", "Replay", "赛事回放", "全场回放"]


async def fetch_bilibili_replays(uid: str = "50329118") -> list[dict[str, Any]]:
    """获取指定 UID 的赛事回放视频（按标题关键词筛选）。

    从 fetch_bilibili_updates 结果中筛选标题包含回放关键词的视频。
    """
    all_videos = await fetch_bilibili_updates(uid)
    replays = []
    for v in all_videos:
        title = v.get("title", "")
        if any(kw.lower() in title.lower() for kw in _REPLAY_KEYWORDS):
            replays.append(v)
    return replays


async def fetch_bilibili_comments() -> list[dict]:
    """UP主评论区发言（待实现）。"""
    return []


async def fetch_bilibili_reply_replies() -> list[dict]:
    """UP主楼中楼回复（待实现）。"""
    return []
