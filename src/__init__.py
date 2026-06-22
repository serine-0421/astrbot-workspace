"""LoL Notifier workspace — AstrBot 插件项目.

项目结构:
    src/
    └── astrbot_plugin_lol_notifier/   ← 插件包
        ├── fetcher/   → 数据抓取（citoapi / B站 / 微博）
        ├── formatter/ → 消息格式化（文本 / HTML 图片）
        └── models.py  → 数据模型

入口: main.py（AstrBot 加载点）
测试: TEST.md（含全端点连通性脚本）
"""