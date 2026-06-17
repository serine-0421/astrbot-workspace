"""State management for match push notifications."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class NotificationState:
    # ── 比赛提醒节点 ──
    first_match_reminded: bool = False
    pre_match_notice: dict[str, bool] = field(default_factory=dict)
    bp_round_notice: dict[str, list[int]] = field(default_factory=dict)
    post_round_notice: dict[str, list[int]] = field(default_factory=dict)
    elimination_updates: dict[str, dict[str, str]] = field(default_factory=dict)

    # ── 第三方平台动态去重 ──
    bilibili_updates: set[str] = field(default_factory=set)    # LOL官号视频 BV 号
    bilibili_bp_dynamics: set[str] = field(default_factory=set)  # BLG BP 动态 ID
    weibo_updates: set[str] = field(default_factory=set)         # 微博帖子 ID

    def __post_init__(self) -> None:
        """KV 持久化时集合会被序列化为 list，加载时还原为 set。"""
        for attr in ("bilibili_updates", "bilibili_bp_dynamics", "weibo_updates"):
            val = getattr(self, attr)
            if isinstance(val, list):
                setattr(self, attr, set(val))


def default_state() -> NotificationState:
    return NotificationState()
