# astrbot_plugin_lol_notifier

🎮 **LoL Notifier** — AstrBot 的 LCK / LPL 赛事推送与查询插件

当前版本已经完成插件结构迁移：命令、模型、格式化、图片渲染和调度器骨架都已切换为 LoL 赛事语义。后续只需要在 `src/astrbot_plugin_lol_notifier/api.py` 接入真实数据源，即可继续扩展自动推送与详细赛事查询能力。

---

## 功能方向

### 查询命令

所有指令以 `/lol` 开头：

| 指令 | 说明 |
|---|---|
| `/lol help` | 显示帮助信息 |
| `/lol schedule [lck|lpl] [regular|playoff] [season]` | 赛程查询 |
| `/lol next [lck|lpl] [regular|playoff] [season]` | 下一场完整时间表 |
| `/lol result [lck|lpl] [regular|playoff] [round]` | 比赛结果 |
| `/lol bp [lck|lpl] [regular|playoff] [round]` | 单局 BP |
| `/lol detail [lck|lpl] [regular|playoff] [round]` | 比赛详细信息 |
| `/lol standings [lck|lpl] [regular|playoff] [season]` | 排名 / 积分榜 |
| `/lol subscribe` | 订阅当前会话的自动推送 |
| `/lol unsubscribe` | 取消当前会话的自动推送 |
| `/lol test [season]` | 测试当前插件骨架 |

### 后续推送方向

| 触发时机 | 推送内容 |
|---|---|
| 常规赛 / 淘汰赛开赛前 | 赛程提醒 |
| 比赛结束后 | 比赛结果 |
| 每局结束后 | 单局 BP |
| 关键对局结束后 | 比赛详细信息 |
| 赛季进行中 | 排名 / 积分榜 |

---

## 安装

在 AstrBot 插件管理页面中搜索 `astrbot_plugin_lol_notifier` 并安装，或手动克隆本仓库到插件目录：

```bash
git clone https://github.com/MareDevi/astrbot_plugin_lol_notifier
```

---

## 说明

当前代码已完成结构替换，但还没有接入真实的 LCK / LPL 数据源。你接下来可以把赛事数据提供方式补进 `src/astrbot_plugin_lol_notifier/api.py`，其余层已经按这个目标预留好了接口。

## 在 AstrBot 中运行

1. 将整个外层仓库目录放到 AstrBot 的插件目录中，确保外层 [main.py](main.py) 和内层 [astrbot_plugin_lol-master/main.py](astrbot_plugin_lol-master/main.py) 都保留。
2. 在 AstrBot 管理界面启用插件后，使用 `/lol help` 查看命令。
3. 后续如果要接入真实赛事数据，只需要继续扩展 [src/astrbot_plugin_lol_notifier/api.py](src/astrbot_plugin_lol_notifier/api.py)。
