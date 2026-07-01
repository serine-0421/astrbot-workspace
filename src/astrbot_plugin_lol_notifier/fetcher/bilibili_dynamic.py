"""Bilibili 动态抓取器 — 向后兼容包装。

所有实际抓取逻辑已迁移到 bilibili.py 的 fetch_bilibili_dynamics(uid)。
此模块保留 fetch_blg_bp_dynamics() 作为 BLG BP 专用便捷函数。
"""

from __future__ import annotations

from typing import Any

from .bilibili import fetch_bilibili_dynamics

# BLG 电子竞技俱乐部 UID（新）
BLG_UID = "268999208"


async def fetch_blg_bp_dynamics() -> list[dict[str, Any]]:
    """获取 BLG电子竞技俱乐部 (UID 268999208) 的图文动态并筛选含"BP"关键词的内容。

    使用共享抓取器 fetch_bilibili_dynamics()，仅筛选 DYNAMIC_TYPE_DRAW + BP 关键词。

    Returns:
        [{"dynamic_id":"...", "text":"...", "images":[...], "url":"...", "timestamp":...}]
    """
    items = await fetch_bilibili_dynamics(BLG_UID)

    results: list[dict[str, Any]] = []
    for item in items:
        # 仅处理图文动态
        if item.get("type") != "DYNAMIC_TYPE_DRAW":
            continue
        # 关键词匹配
        if "BP" not in item.get("text", ""):
            continue
        results.append(item)
    return results
