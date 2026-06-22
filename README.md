# 🎮 AstrBot LoL Notifier

LoL 电竞赛事推送与查询插件 — **128+ API 端点** × **21 个数据类别** × **28+ 查询命令**。

覆盖 **LCK / LPL / LEC / LCS / MSI / Worlds** 等 14 个赛区，从赛程、排名、实时比分、BP 阵容到选手生涯、战队交手记录、英雄统计、全球战力排行榜、转会动态、锦标赛对阵，一站式查询。

集成 B 站官号视频监控、BLG 战队 BP 图文推送、微博赛前海报抓取。

---

## ✨ 功能总览

### 21 大数据类别

| # | 类别 | 说明 | 端点数 |
|:--|:--|:--|:--|
| 1 | **Leagues** | 联赛信息查询 | 2 |
| 2 | **Schedule** | 赛程（完整/今日/本周/即将/已完成） | 5 |
| 3 | **Live** | 实时比赛（窗口/统计/时间线/事件流） | 5 |
| 4 | **Matches** | 比赛详情、BP、时间线 | 6 |
| 5 | **Games** | 对局级数据 | 8 |
| 6 | **Teams** | 战队信息/阵容/统计/交手/英雄 | 9 |
| 7 | **Players** | 选手信息/统计/生涯/英雄池 | 7 |
| 8 | **Tournaments** | 锦标赛/积分榜/对阵/MVP | 9 |
| 9 | **Standings** | 积分榜/排名 | 3 |
| 10 | **Champions** | 英雄统计/登场率/对局 | 4 |
| 11 | **Rankings** | 全球战力GPR/选手排名/战队排名 | 3 |
| 12 | **Leaderboards** | 8 项指标排行榜 | 8 |
| 13 | **History** | 世界赛/MSI/赛区历史 | 3 |
| 14 | **Transfers** | 转会动态 | 2 |
| 15 | **Search** | 战队/选手/锦标赛/比赛搜索 | 4 |
| 16 | **Trending** | 热门趋势（综合/选手/战队/英雄） | 4 |
| 17 | **Static Data** | 英雄/装备/符文/召唤师技能/版本 | 6 |
| 18 | **Regions** | 区域信息 | 1 |
| 19 | **Roles** | 位置信息 | 1 |
| 20 | **Records** | 赛事记录/里程碑 | 2 |
| 21 | **Awards** | 奖项/MVP/全明星/季后赛 | 4 |

### 消息来源集成

| 来源 | 功能 | 触发 |
|:--|:--|:--|
| 🔔 B站 LOL 官号 | 官方视频投稿推送 | 自动（订阅后） |
| 🔵 B站 BLG 官号 | BP 图文动态推送 | 自动（订阅后） |
| 📰 微博 | LPL 赛前海报推送 | 自动（订阅后） |

---

## 📦 安装

```bash
cd AstrBot/data/plugins
git clone https://github.com/MareDevi/astrbot_plugin_lol_notifier.git
```

依赖：`httpx`、`aiohttp`、`pillow`

---

## 🔑 API Key 配置

LoL Esports 赛事数据（赛程/排名/比赛详情/BP/实时比分）通过 **citoapi** 获取。

### 配置方式（任选一种）

**方式 1：环境变量（推荐）**
```bash
# Windows PowerShell
$env:CITO_API_KEY = "cito_xxxxxxxx"
# Linux / macOS
export CITO_API_KEY="cito_xxxxxxxx"
```

**方式 2：插件配置文件** — 在 AstrBot 插件配置中添加 `"cito_api_key": "cito_xxxxxxxx"`

**方式 3：命令行动态设置** — `/lol apikey cito_xxxxxxxx`

> 💡 插件内置了一个默认 Key，不配置也可直接使用。但建议配置自己的 Key 以获得更稳定的服务。

---

## 📖 命令参考

### 🔹 赛程 & 比赛

| 命令 | 说明 | 示例 |
|:--|:--|:--|
| `/lol schedule [league]` | 查询赛区完整赛程 | `/lol schedule lpl` |
| `/lol next [league]` | 下一场比赛 | `/lol next lck` |
| `/lol live [league]` | 实时比赛（击杀/经济/塔/龙/男爵） | `/lol live` |
| `/lol result [league]` | 最近比赛结果 | `/lol result lpl` |
| `/lol bp [league]` | 最近比赛 BP 阵容 | `/lol bp lck` |
| `/lol detail [league]` | 最近比赛完整详情 | `/lol detail` |
| `/lol standings [league]` | 积分榜/排名 | `/lol standings lck` |
| `/lol today` | 今日所有赛程 | `/lol today` |
| `/lol week` | 本周所有赛程 | `/lol week` |

### 🔹 战队 — `/lol team`

| 子命令 | 说明 | 示例 |
|:--|:--|:--|
| `/lol team search <关键词>` | 搜索战队 | `/lol team search T1` |
| `/lol team info <id>` | 战队详情 | `/lol team info {team_id}` |
| `/lol team roster <id>` | 战队阵容 | `/lol team roster {team_id}` |
| `/lol team matches <id>` | 战队近期比赛 | `/lol team matches {team_id}` |
| `/lol team stats <id>` | 战队统计数据 | `/lol team stats {team_id}` |
| `/lol team h2h <a> <b>` | 两队历史交手 | `/lol team h2h T1 GEN` |

### 🔹 选手 — `/lol player`

| 子命令 | 说明 | 示例 |
|:--|:--|:--|
| `/lol player search <关键词>` | 搜索选手 | `/lol player search Faker` |
| `/lol player info <id>` | 选手详情 | `/lol player info {player_id}` |
| `/lol player stats <id>` | 选手赛季统计 | `/lol player stats {player_id}` |
| `/lol player champions <id>` | 选手英雄池 | `/lol player champions {player_id}` |

### 🔹 锦标赛 — `/lol tournament`

| 子命令 | 说明 | 示例 |
|:--|:--|:--|
| `/lol tournament info <id>` | 锦标赛详情 | `/lol tournament info {id}` |
| `/lol tournament standings <id>` | 锦标赛积分榜 | `/lol tournament standings {id}` |
| `/lol tournament bracket <id>` | 淘汰赛对阵图 | `/lol tournament bracket {id}` |
| `/lol tournament mvp <id>` | 锦标赛 MVP | `/lol tournament mvp {id}` |

### 🔹 英雄 — `/lol champion`

| 子命令 | 说明 | 示例 |
|:--|:--|:--|
| `/lol champion stats [league]` | 英雄统计数据 | `/lol champion stats lck` |
| `/lol champion presence [league]` | 英雄登场率/禁用率 | `/lol champion presence lck` |

### 🔹 排名 — `/lol ranking`

| 子命令 | 说明 | 示例 |
|:--|:--|:--|
| `/lol ranking gpr` | 全球战力排名 (GPR) | `/lol ranking gpr` |
| `/lol ranking players <指标>` | 选手排名 | `/lol ranking players kda` |

### 🔹 排行榜 — `/lol leaderboard`

```
/lol leaderboard <指标> [league]
```

支持 8 项指标：`kda` `kills` `deaths` `assists` `cs` `gold` `vision` `damage`

| 示例 | 说明 |
|:--|:--|
| `/lol leaderboard kda lck` | LCK KDA 排行榜 |
| `/lol leaderboard kills lck` | LCK 击杀榜 |

### 🔹 其他数据查询

| 命令 | 说明 |
|:--|:--|
| `/lol trending` | 热门趋势概览 |
| `/lol history <worlds\|msi>` | 世界赛 / MSI 历史数据 |
| `/lol transfers [league]` | 转会动态 |
| `/lol records` | 赛事记录 |

### 🔹 管理

| 命令 | 说明 |
|:--|:--|
| `/lol subscribe` | 订阅自动推送 |
| `/lol unsubscribe` | 取消订阅 |
| `/lol apikey` | 查看 Key 状态 |
| `/lol apikey <key>` | 手动设置 API Key |
| `/lol test` | 测试连接 |

### 支持的赛区 (league)

```
lck  lpl  lec  lcs  lco  lcl  ljl  pcs  vcs  cblol  lla  tcl  msi  worlds
```

---

## ⚙️ 配置项

| 配置项 | 类型 | 默认值 | 说明 |
|:--|:--|:--|:--|
| `cito_api_key` | str | `""` | citoapi Key |
| `enable_image_render` | bool | `false` | HTML 渲染图片 |
| `enable_match_notifications` | bool | `true` | 赛事自动推送 |
| `bilibili_uid` | str | `"50329118"` | B站 LOL 官号 UID |
| `enable_bilibili_video_push` | bool | `true` | 推送 B站视频更新 |
| `bilibili_blg_uid` | str | `"545271146"` | B站 BLG 官号 UID |
| `enable_bilibili_blg_bp_push` | bool | `true` | 推送 BLG BP 动态 |
| `weibo_uids` | list | `["6537214902"]` | 微博号 UID 列表 |
| `weibo_cookie` | str | `""` | 微博 Cookie |
| `enable_weibo_poster_push` | bool | `true` | 推送微博海报 |

---

## 🏗 项目结构

```
astrbot_plugin_lol_notifier/
├── main.py                     # AstrBot 插件入口（28+ 命令）
├── metadata.yaml               # 插件元数据
├── pyproject.toml              # 项目配置 & 依赖
├── _conf_schema.json           # 配置 Schema
├── README.md                   # 本文件
├── TEST.md                     # 本地测试文档
├── data/
│   ├── cmd_config.json         # 指令配置
│   ├── t2i_templates/          # HTML 渲染模板
│   └── temp/tool_images/
└── src/
    └── astrbot_plugin_lol_notifier/
        ├── __init__.py         # 包导出
        ├── config.py           # 配置管理
        ├── models.py           # 数据模型（dataclass）
        ├── image_renderer.py   # HTML → 图片
        ├── scheduler.py        # 后台推送调度
        ├── state.py            # 去重状态管理
        ├── utils.py            # 工具函数
        ├── fetcher/            # 数据抓取层
        │   ├── __init__.py
        │   ├── api.py               # 数据访问封装（41 个包装函数）
        │   ├── lolesports.py        # citoapi 网络层（103 个 fetch 函数）
        │   ├── bilibili.py          # B站 API
        │   ├── bilibili_dynamic.py  # B站动态 API
        │   └── weibo.py             # 微博 API
        └── formatter/          # 格式化层
            ├── __init__.py
            ├── card.py         # 卡片格式化
            └── message.py      # 消息格式化（36 个 formatter）
```

### 数据流

```
用户命令 (/lol xxx)
    ↓
main.py → LoLNotifierPlugin（命令解析 & 路由）
    ↓
api.py → 数据访问层（league 校验、数据过滤、Result 封装）
    ↓
lolesports.py → citoapi HTTP 请求（httpx AsyncClient）
    ↓
citoapi (https://api.citoapi.com/api/v1)
    ↓
message.py → 格式化输出（文本/HTML/图片）
    ↓
AstrBot 消息通道（QQ / Telegram / WebChat）
```

---

## 🧪 测试

详见 [TEST.md](./TEST.md)，包含：

- **全端点连通性测试** — 一个脚本验证 40+ 端点 HTTP 状态
- **按类别逐类测试** — 每类端点的 curl 示例
- **Python 脚本测试** — 无需 AstrBot，直接调用 fetcher 层
- **AstrBot 命令清单** — 全部 28+ 命令的测试 checkbox
- **错误处理验证** — 无效 Key / 不支持赛区 / 缺参数等场景

---

## ❓ FAQ

**Q: 支持哪些赛区？**
A: 14 个：LCK、LPL、LEC、LCS、LCO、LCL、LJL、PCS、VCS、CBLOL、LLA、TCL、MSI、Worlds。赛区 slug 自动映射到 citoapi 格式。

**Q: 赛程查询返回空或报错？**
A: `/lol apikey` 检查 Key 状态。citoapi Key 长期有效。

**Q: `/lol live` 返回"没有正在进行的比赛"？**
A: 仅在比赛进行中才有实时数据。请确认当前是否有 League 正在比赛。

**Q: 只想要自动推送？**
A: 执行 `/lol subscribe`，调度器在后台自动推送，无需主动查询。

**Q: 数据来源可靠吗？**
A: 赛事数据来自 citoapi (`https://api.citoapi.com/api/v1`)，B站/微博来自平台公开接口。

**Q: 战队/选手 ID 从哪里获取？**
A: 使用 `/lol team search <关键词>` 或 `/lol player search <关键词>` 获取 ID。

---

## 📝 License

MIT © [MareDevi](https://github.com/MareDevi)
