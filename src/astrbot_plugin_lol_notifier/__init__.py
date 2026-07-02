"""LoL Notifier plugin package — AstrBot 插件.

本包可独立于 AstrBot 使用（fetcher/formatter/models 均无 AstrBot 依赖）,
便于本地脚本测试。

核心模块:
    fetcher/   — 数据抓取（PandaScore + B站/微博）
    formatter/ — 消息格式化（36 text formatters + 5 HTML renderers）
    models.py  — 数据模型（dataclass + Result 模式）
    config.py  — 插件配置管理
    scheduler.py — 后台推送调度
    image_renderer.py — HTML → 图片渲染
"""

from . import fetcher, formatter, image_renderer, models

__all__ = ["fetcher", "formatter", "image_renderer", "models"]
