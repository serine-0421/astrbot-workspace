"""Plugin configuration helpers for LoL notifier."""

from __future__ import annotations

from typing import Any


# ═══════════════════════════════════════════════════
#  B站推送账号定义
# ═══════════════════════════════════════════════════

BILIBILI_ACCOUNTS: list[dict[str, str]] = [
    {"uid": "50329118",  "name": "哔哩哔哩英雄联盟赛事", "key": "lol"},
    {"uid": "108532523", "name": "英雄联盟赛事",         "key": "lolesports"},
    {"uid": "268999208", "name": "BLG电子竞技俱乐部",    "key": "blg"},
]

# 每个账号各推送类型的默认开关
# live=直播  video=视频  article=图文动态
BILIBILI_DEFAULT_PUSH: dict[str, dict[str, bool]] = {
    "lol":        {"video": True,  "article": True,  "live": False},
    "lolesports": {"video": False, "article": True,  "live": False},
    "blg":        {"video": True,  "article": True,  "live": False},
}


def _gen_bilibili_defaults() -> dict[str, Any]:
    """根据 BILIBILI_DEFAULT_PUSH 生成 flat 默认值。"""
    d: dict[str, Any] = {}
    for acct in BILIBILI_ACCOUNTS:
        key = acct["key"]
        defaults = BILIBILI_DEFAULT_PUSH.get(key, {"video": False, "article": False, "live": False})
        for ptype in ("video", "article", "live"):
            d[f"bilibili_push_{key}_{ptype}"] = defaults.get(ptype, False)
    return d


DEFAULT_CONFIG: dict[str, Any] = {
    "follow_teams": [],
    "enable_image_render": False,
    "enable_match_notifications": True,
    # ── citoapi（赛程/排名/比赛详情/实时数据） ──
    # API Key 优先级: 环境变量 CITO_API_KEY > 此处的 cito_api_key > 内置 Key
    # citoapi Key 长期有效，无需刷新
    "cito_api_key": "",
    # ── B站: 多账号推送开关（由 _gen_bilibili_defaults 生成） ──
    **_gen_bilibili_defaults(),
    "bilibili_check_interval": 60,
    # ── 微博: 英雄联盟赛事 (UID 6537214902)（海报推送） ──
    "weibo_uids": [
        "6537214902",  # 英雄联盟赛事
    ],
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


# ── B站推送开关查询 ──

def is_bilibili_push_enabled(config: Any, account_key: str, push_type: str) -> bool:
    """查询某个账号的某种推送是否开启。

    push_type: 'video' | 'article' | 'live'
    """
    config_key = f"bilibili_push_{account_key}_{push_type}"
    default_val = BILIBILI_DEFAULT_PUSH.get(account_key, {}).get(push_type, False)
    return bool(config.get(config_key, default_val)) if config else default_val


def is_any_bilibili_push_enabled(config: Any) -> bool:
    """是否有任意 B站推送开启。"""
    if config is None:
        return any(
            BILIBILI_DEFAULT_PUSH.get(a["key"], {}).get(pt, False)
            for a in BILIBILI_ACCOUNTS
            for pt in ("video", "article", "live")
        )
    for acct in BILIBILI_ACCOUNTS:
        for pt in ("video", "article", "live"):
            if is_bilibili_push_enabled(config, acct["key"], pt):
                return True
    return False


# ── 微博 ──

def get_weibo_uids(config: Any) -> list[str]:
    return list(config.get("weibo_uids", DEFAULT_CONFIG["weibo_uids"])) if config else DEFAULT_CONFIG["weibo_uids"]


def is_weibo_poster_push_enabled(config: Any) -> bool:
    return bool(config.get("enable_weibo_poster_push", True)) if config else True



