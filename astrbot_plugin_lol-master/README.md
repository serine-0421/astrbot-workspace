# 🎮 LoL Notifier — AstrBot 赛事推送与查询插件

LCK / LPL 英雄联盟赛事自动推送 + 手动词条查询，集成 B 站官号视频监控、BLG 战队 BP 图文推送、微博赛前海报抓取。

---

## 已实现功能

### ✅ 第三方平台自动推送

| 触发源 | 账号 | 推送内容 | 开关配置 |
|--------|------|----------|----------|
| **B 站 LOL 官号** | UID `50329118` | 最新视频投稿（标题 / BV 号 / 封面 / 链接） | `enable_bilibili_video_push` |
| **B 站 BLG 官号** | UID `545271146` | 含 "BP" 关键词的图文动态（文案 + 图片 URL） | `enable_bilibili_blg_bp_push` |
| **微博各队官号** | 可配置 UID 列表 | LPL + 预告 赛前海报（匹配含 "LPL" 和 "预告" 的帖子） | `enable_weibo_poster_push` |

> 推送间隔：B 站 60 秒，微博 300 秒。首次启动静默记录已有内容，不会刷屏。

### 🚧 赛事数据推送（框架就绪，待接入数据源）

| 触发时机 | 推送内容 |
|----------|----------|
| ⏰ 距比赛日 ≤ 24 小时 | 当日赛程 + 对阵表 + 双方战队海报 |
| 🔍 比赛前 30 分钟 | 首发名单 + 历史交手 + 赛前预测 + 双方海报 |
| 🧠 每小局 BP 结束后 | 格式化阵容名单 |
| 📊 每小局结束后 | 简要胜负 + 战报图片 |
| 🏆 比赛结束后 | 最终比分 + MVP / FMVP + B 站回放视频 |
| 🏅 淘汰赛关键节点 | 晋级/淘汰情况 + 后续对阵 |

---

## 指令列表

所有指令以 `/lol` 为前缀。`[]` 内为可选参数，不填时使用默认值。

### 📋 查询命令

| 指令 | 说明 | 示例 |
|------|------|------|
| `/lol help` | 显示完整帮助 | `/lol help` |
| `/lol schedule [lck\|lpl] [regular\|playoff] [season]` | 近期赛程（默认最近 5 场） | `/lol schedule lpl regular 2024` |
| `/lol next [lck\|lpl] [regular\|playoff] [season]` | 下一场比赛完整时间表 | `/lol next lck playoff` |
| `/lol result [lck\|lpl] [regular\|playoff] [round]` | 比赛结果（round 为空 = 最近一场） | `/lol result lpl regular 3` |
| `/lol bp [lck\|lpl] [regular\|playoff] [round]` | 单局 BP 阵容 | `/lol bp lck playoff 1` |
| `/lol detail [lck\|lpl] [regular\|playoff] [round]` | 比赛详细信息 | `/lol detail lpl regular last` |
| `/lol standings [lck\|lpl] [regular\|playoff] [season]` | 排名 / 积分榜 | `/lol standings lck regular 2024` |

### ⚙️ 管理命令

| 指令 | 说明 |
|------|------|
| `/lol subscribe` | 订阅当前群聊/私聊的自动推送 |
| `/lol unsubscribe` | 取消当前会话的自动推送 |
| `/lol test [season]` | 测试插件各项查询功能是否正常 |

---

## 配置项

在 AstrBot 后台 → 插件管理 → LoL Notifier → 配置 中修改，或直接编辑 `_conf_schema.json`。

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `bilibili_uid` | string | `"50329118"` | B 站 LOL 赛事官号 UID |
| `enable_bilibili_video_push` | bool | `true` | 开启 LOL 官号视频推送 |
| `bilibili_blg_uid` | string | `"545271146"` | BLG 电子竞技俱乐部 B 站 UID |
| `enable_bilibili_blg_bp_push` | bool | `true` | 开启 BLG BP 图文动态推送 |
| `bilibili_check_interval` | int | `60` | B 站轮询间隔（秒） |
| `weibo_uids` | list | `["6537214902"]` | 微博监控账号 UID 列表 |
| `enable_weibo_poster_push` | bool | `true` | 开启微博赛前海报推送 |
| `weibo_check_interval` | int | `300` | 微博轮询间隔（秒，建议 ≥ 5 分钟） |
| `weibo_cookie` | string | `""` | 微博登录 Cookie（可选，提高 API 稳定性） |
| `enable_image_render` | bool | `false` | 开启图片渲染模式（需 Pillow） |
| `enable_match_notifications` | bool | `true` | 开启赛事相关推送 |

> **微博 UID 获取方法**：打开目标用户微博主页，URL 中的数字即为 UID。例如 `https://weibo.com/u/6537214902` → UID 为 `6537214902`。

---

## 架构

```
main.py                          ← AstrBot 插件入口，注册命令 + 启动调度器
src/astrbot_plugin_lol_notifier/
├── config.py                    ← 配置读取（B 站 UID、微博 UID、推送开关）
├── state.py                     ← 去重状态管理（已推送的视频/动态/帖子 ID）
├── scheduler.py                 ← 9 种推送时机调度 + 广播
├── api.py                       ← 赛事数据 API 统一入口（待接入）
├── models.py                    ← 数据模型（LeagueMatch / MatchGame / StandingEntry）
├── utils.py                     ← 通用工具（赛区名称规范化）
├── image_renderer.py            ← Pillow 图片渲染
├── fetcher/
│   ├── api.py                   ← 赛事数据获取层骨架
│   ├── bilibili.py              ← B 站 LOL 官号视频抓取（公开 API + WBI 签名双方案）
│   ├── bilibili_dynamic.py      ← B 站 BLG 官号图文动态抓取（type=DRAW + "BP" 关键词）
│   └── weibo.py                 ← 微博 m.weibo.cn 移动端 API 海报抓取
├── formatter/
│   ├── message.py               ← 文本格式化（视频 / 海报 / BP / 赛程 / 结果 等）
│   └── card.py                  ← 图片卡片样式渲染
└── tests/
    └── test_fixes.py            ← 31 个冒烟测试
```

### 抓取器设计

- **B 站视频** (`bilibili.py`)：优先公开 API → 限频时自动降级 WBI 签名，首次运行记录已有视频不推送，后续只推送 180s 内的新视频
- **B 站 BLG 动态** (`bilibili_dynamic.py`)：调用 `x/polymer/web-dynamic/v1/feed/space` 接口，仅保留 `DYNAMIC_TYPE_DRAW`（图文）+ 包含 "BP" 的条目
- **微博海报** (`weibo.py`)：调用 `m.weibo.cn/api/container/getIndex` 移动端接口，去 HTML 标签后用 "LPL" + "预告" 双关键词匹配，提取图片 URL

---

## 安装

### 方法一：AstrBot 插件市场

在 AstrBot 管理面板 → 插件管理 → 搜索 `astrbot_plugin_lol_notifier` → 安装。

### 方法二：手动安装

```bash
# 进入 AstrBot 插件目录
cd AstrBot/addons/plugins/
git clone https://github.com/MareDevi/astrbot_plugin_lol_notifier
```

安装后在 AstrBot 管理面板启用插件即可。发送 `/lol help` 验证是否正常工作。

---

## 后续接入指南

赛事数据模块（`api.py` / `fetcher/api.py`）当前返回 `"LoL 数据源尚未接入"`。要启用完整赛事推送：

1. 在 `fetcher/api.py` 中实现 `get_schedule`、`get_match_result`、`get_match_bp`、`get_match_detail`、`get_standings` 五个函数
2. 所有函数返回 `Success[list[LeagueMatch]] | Failure` 类型
3. 接入后可选的赛事数据来源：PandaScore API、Bayesesports、官方赛事 API 等

---

## License

MIT License — 详见 [LICENSE](LICENSE)

