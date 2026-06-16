"""State management for match push notifications."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class NotificationState:
    # 比赛提醒节点
    first_match_reminded: bool = False
    pre_match_notice: dict[str, bool] = field(default_factory=dict)
    bp_round_notice: dict[str, list[int]] = field(default_factory=dict)
    post_round_notice: dict[str, list[int]] = field(default_factory=dict)
    elimination_updates: dict[str, dict[str, str]] = field(default_factory=dict)
    # 第三方平台动态去重
    bilibili_updates: set[str] = field(default_factory=set)
    weibo_updates: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        """KV 持久化时集合会被序列化为 list，加载时还原为 set。"""
        if isinstance(self.bilibili_updates, list):
            self.bilibili_updates = set(self.bilibili_updates)
        if isinstance(self.weibo_updates, list):
            self.weibo_updates = set(self.weibo_updates)


def default_state() -> NotificationState:
    return NotificationState()
