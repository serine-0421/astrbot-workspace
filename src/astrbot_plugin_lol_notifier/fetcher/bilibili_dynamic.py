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

# B站 Cookie
_bilibili_cookie: str = ""


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
