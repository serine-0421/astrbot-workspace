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
    elimination_updates: dict[str, str] = field(default_factory=dict)  # 淘汰赛/实时比赛状态指纹

    # ── 每日赛程 & 赛前预告 ──
    daily_schedule_sent_date: str = ""  # 已推送每日赛程的北京日期 YYYY-MM-DD
    pre_match_10min_notified: set[str] = field(default_factory=set)  # 已推送 10min 预告的 match_id

    # ── 第三方平台动态去重 ──
    # 多账号 B站推送去重: uid → {id, ...}
    bilibili_video_seen: dict[str, set[str]] = field(default_factory=dict)     # uid → {bvid, ...}
    bilibili_dynamic_seen: dict[str, set[str]] = field(default_factory=dict)   # uid → {dynamic_id, ...}
    bilibili_live_state: dict[str, bool] = field(default_factory=dict)          # uid → 已通知开播?
    weibo_updates: set[str] = field(default_factory=set)  # 微博帖子 ID

    def _ensure_sets(self, d: dict[str, list | set]) -> dict[str, set[str]]:
        """将 KV 反序列化后的 list 还原为 set。"""
        return {k: set(v) if isinstance(v, list) else v for k, v in d.items()}

    def __post_init__(self) -> None:
        """KV 持久化时集合会被序列化为 list，加载时还原为 set。"""
        for attr in ("bilibili_video_seen", "bilibili_dynamic_seen"):
            val = getattr(self, attr)
            if isinstance(val, dict):
                setattr(self, attr, self._ensure_sets(val))
        if isinstance(self.weibo_updates, list):
            self.weibo_updates = set(self.weibo_updates)
        if isinstance(self.pre_match_10min_notified, list):
            self.pre_match_10min_notified = set(self.pre_match_10min_notified)


def default_state() -> NotificationState:
    return NotificationState()
