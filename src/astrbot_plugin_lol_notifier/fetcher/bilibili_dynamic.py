"""Bilibili 动态抓取器 — BLG 电子竞技俱乐部 BP 图文推送。

仅识别图文形式动态（非视频），如果文案中出现"BP"关键词则推送。
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx

from astrbot.api import logger

# BLG 电子竞技俱乐部 UID
BLG_UID = "545271146"

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

# B站 Cookie（硬编码，与 bilibili.py 共用）
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
    "CURRENT_FNVAL=2000; "
    "bp_t_offset_1078666620=1214469777527930880; "
    "bmg_af_switch=1; "
    "bmg_src_def_domain=i2.hdslb.com; "
    "bmg_af_sc={\"none\":{\"on\":1,\"def\":\"i2.hdslb.com\"},\"sgp\":{\"on\":1,\"def\":\"i2-sgp.hdslb.com\"}}; "
    "bili_ticket=eyJhbGciOiJIUzI1NiIsImtpZCI6InMwMyIsInR5cCI6IkpXVCJ9."
    "eyJleHAiOjE3ODMwNzE4MTUsImlhdCI6MTc4MjgxMjU1NSwicGx0IjotMX0."
    "keuaYqkGg_rI4PGiC0uPcIMXIYzpUuuhYoWEBiHgtEw; "
    "bili_ticket_expires=1783071755; "
    "SESSDATA=ecab67ea%2C1798364616%2C82431%2A61CjCo49e9qpHmSccU9TV28XeGLbOcwjGjHVaplqzfliZ3ygJx_mMAcj6-5-VfqP5HfEwSVndXRUZJM0lyMldMMmhtMmxuQWNkeFl2WWJHeVBleEl6T2pybU96SmhTV2gxZDNNQk00TmVJMnpwa1g2NFBKZ3dxZ2xSYko4SFBSUzlQWWJNU0lEY1p3IIEC; "
    "bili_jct=b2505b446532086ef41213f4b2bd9aa8; "
    "sid=qburvfgk; "
    "home_feed_column=4; "
    "browser_resolution=1357-956; "
    "b_lsid=BE586282_19F17EACF7F"
)
_bilibili_cookie: str = _DEFAULT_COOKIE or os.environ.get("BILIBILI_COOKIE", "")


def set_bilibili_cookie(cookie: str) -> None:
    """设置 B站 Cookie。"""
    global _bilibili_cookie
    _bilibili_cookie = (cookie or "").strip()


def _build_headers(referer: str = "https://www.bilibili.com") -> dict[str, str]:
    """构建带 Origin 的请求头。"""
    headers = {
        "User-Agent": _USER_AGENT,
        "Referer": referer,
        "Origin": "https://www.bilibili.com",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    cookie = _bilibili_cookie or os.environ.get("BILIBILI_COOKIE", "")
    if cookie:
        headers["Cookie"] = cookie
    return headers


async def fetch_blg_bp_dynamics() -> list[dict[str, Any]]:
    """获取 BLG 官号的图文动态，筛选含"BP"关键词的内容。

    Returns:
        [{
            "dynamic_id": "123456",
            "text": "BP阵容公布：...",
            "images": ["https://i0.hdslb.com/..."],
            "url": "https://t.bilibili.com/123456",
            "timestamp": 1234567890,
        }]
    """
    url = "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space"
    params = {"host_mid": BLG_UID, "offset": ""}
    headers = _build_headers(f"https://space.bilibili.com/{BLG_UID}/dynamic")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params, headers=headers)
            data = resp.json()

        if data.get("code") != 0:
            code = data.get("code")
            msg = data.get("message", "")
            if code == -352:
                logger.warning(
                    "[BLG] ⚠️ 动态 API 风控 (-352): Cookie 无效或缺失。"
                    "请配置 bilibili_cookie"
                )
            else:
                logger.debug(f"[BLG] Dynamic API error {code}: {msg}")
            return []

        items = data.get("data", {}).get("items", [])
        return _filter_bp_draw_dynamics(items)

    except Exception as e:
        logger.debug(f"[BLG] Dynamic API exception: {e}")
        return []


def _filter_bp_draw_dynamics(items: list[dict]) -> list[dict[str, Any]]:
    """从动态列表中筛选：图文类型 + 包含"BP"关键词。"""
    results: list[dict[str, Any]] = []

    for item in items:
        # 仅处理图文动态（DYNAMIC_TYPE_DRAW）
        dyn_type = item.get("type", "")
        if dyn_type != "DYNAMIC_TYPE_DRAW":
            continue

        modules = item.get("modules", {}).get("module_dynamic", {})
        major = modules.get("major", {})
        desc = modules.get("desc", {})

        # 确认 major 类型是图文
        if major.get("type") != "MAJOR_TYPE_DRAW":
            continue

        # 提取文案
        text = desc.get("text", "")

        # 关键词匹配："BP"
        if "BP" not in text:
            continue

        # 提取图片
        images: list[str] = []
        draw_items = major.get("draw", {}).get("items", [])
        for img in draw_items:
            src = img.get("src", "")
            if src:
                images.append(src)

        dynamic_id = item.get("id_str", "")
        results.append({
            "dynamic_id": dynamic_id,
            "text": text.strip(),
            "images": images,
            "url": f"https://t.bilibili.com/{dynamic_id}",
            "timestamp": modules.get("module_author", {}).get("pub_ts", 0),
        })

    return results
