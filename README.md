# 🎮 AstrBot LoL Notifier

LoL 电竞赛事推送与查询插件，覆盖 **LCK / LPL / LEC / LCS / MSI / Worlds** 等 14 个赛区，提供赛程、实时比分、积分榜、战队详情。同时集成哔哩哔哩英雄联盟赛事、英雄联盟赛事、BLG电子竞技俱乐部三个 B 站账号（视频·图文·直播）及英雄联盟赛事微博的赛前海报抓取，支持每种内容类型独立开关。

> 💡 **开箱即用** — 插件内置 API Key，安装后直接使用，无需额外配置。
> 📡 数据来源：[PandaScore](https://pandascore.co)（主） + [citoapi](https://api.citoapi.com/api/v1/lol)（备用）

### 🔄 数据流架构

```mermaid
flowchart LR
    CMD["/lol 命令"] --> API["api.py<br/>统一入口"]
    API --> PS["PandaScore<br/>主数据源<br/>Bearer Token"]
    API --> CITO["citoapi<br/>备用回退<br/>x-api-key"]
    PS -->|成功| RESULT["返回结果"]
    PS -->|失败| CITO
    CITO --> RESULT
```

---

## 📦 安装

```bash
cd AstrBot/data/plugins
git clone https://github.com/MareDevi/astrbot_plugin_lol_notifier.git
```

依赖：
- [AstrBot](https://github.com/AstrBotDevs/AstrBot) >= v4
- `httpx`、`aiohttp`、`pillow`

---

## 📖 命令参考

所有命令以 `/lol` 开头。`[ ]` 表示可选参数，`< >` 表示必填参数。**未指定赛区时默认使用 LPL**。

### 🔹 lol matches — 比赛

> PandaScore: `GET /lol/matches` · `GET /lol/matches/running` · `GET /lol/matches/past` · `GET /lol/matches/upcoming` · `GET /lol/matches/{id}`

| 命令 | 说明 | 示例 |
|:--|:--|:--|
| `/lol schedule [赛区] [stage] [season]` | 查询赛区赛程，按距今天最近排序（默认 LPL，最近 5 场） | `/lol schedule lpl` |
| `/lol next [赛区] [stage] [season]` | 下一场未开赛的完整时间表 | `/lol next lck` |
| `/lol today [赛区]` | 今日所有赛程 | `/lol today` `/lol today lpl` |
| `/lol live [赛区]` | 正在进行的实时比赛（击杀/经济/塔/龙） | `/lol live` `/lol live lck` |
| `/lol result [赛区] [stage] [round]` | 比赛结果（默认最近一场） | `/lol result lpl` `/lol result lck playoff 3` |
| `/lol detail [赛区] [stage] [round]` | 比赛完整详情（含对局数据） | `/lol detail lck` |

### 🔹 lol games — 对局

> PandaScore: `GET /lol/games/{id}` · `GET /lol/games/{id}/events` · `GET /lol/games/{id}/frames` · `GET /lol/matches/{id}/games`

| 命令 | 说明 | 示例 |
|:--|:--|:--|
| `/lol game info <game_id>` | 单局详情 | `/lol game info 123456` |
| `/lol game events <game_id>` | 对局事件 | `/lol game events 123456` |
| `/lol game frames <game_id>` | 对局帧数据 | `/lol game frames 123456` |
| `/lol match games <match_id>` | 比赛所有对局 | `/lol match games 789012` |

### 🔹 lol stats — 统计数据

> PandaScore: `GET /lol/matches/{id}/players/stats` · `GET /lol/players/{id}/stats` · `GET /lol/teams/{id}/stats` · `GET /lol/series/{id}/teams/stats` · `GET /lol/tournaments/{id}/teams/{id}/stats`

| 命令 | 说明 | 示例 |
|:--|:--|:--|
| `/lol match stats <match_id>` | 比赛选手统计 | `/lol match stats 789012` |
| `/lol player stats <player_id>` | 选手统计 | `/lol player stats 456` |
| `/lol team stats <team_id>` | 战队统计 | `/lol team stats 123` |

### 🔹 lol teams — 战队

> PandaScore: `GET /lol/teams` · `GET /lol/series/{id}/teams`

| 命令 | 说明 | 示例 |
|:--|:--|:--|
| `/lol team info [战队名]` | 查看所有战队，或按名称筛选 | `/lol team info` `/lol team info T1` |

### 🔹 lol players — 选手

> PandaScore: `GET /lol/players`

| 命令 | 说明 | 示例 |
|:--|:--|:--|
| `/lol players [赛区]` | 选手列表 | `/lol players lck` |
| `/lol player <id>` | 选手信息 | `/lol player 456` |

### 🔹 lol series — 系列赛

> PandaScore: `GET /lol/series` · `GET /lol/series/past` · `GET /lol/series/running` · `GET /lol/series/upcoming`

| 命令 | 说明 | 示例 |
|:--|:--|:--|
| `/lol series [赛区] [status]` | 系列赛列表（status: past/running/upcoming） | `/lol series lck` `/lol series lck running` |
| `/lol series detail <id>` | 系列赛详情 | `/lol series detail 42` |

### 🔹 lol tournaments — 锦标赛

> PandaScore: `GET /lol/tournaments` · `GET /lol/tournaments/past` · `GET /lol/tournaments/running` · `GET /lol/tournaments/upcoming`

| 命令 | 说明 | 示例 |
|:--|:--|:--|
| `/lol tournaments [赛区] [status]` | 锦标赛列表 | `/lol tournaments lck` |
| `/lol tournament <id>` | 锦标赛详情 | `/lol tournament 15` |
| `/lol standings [赛区] [stage] [season]` | 积分榜 / 排名 | `/lol standings lck` `/lol standings lpl` |

### 🔹 lol champions — 英雄

> PandaScore: `GET /lol/champions` · `GET /lol/champions/{id}`

| 命令 | 说明 | 示例 |
|:--|:--|:--|
| `/lol champions [version]` | 英雄列表 | `/lol champions` `/lol champions 14.10` |
| `/lol champion <id_or_slug>` | 单个英雄 | `/lol champion Aatrox` |

### 🔹 lol items — 装备

> PandaScore: `GET /lol/items` · `GET /lol/items/{id}`

| 命令 | 说明 | 示例 |
|:--|:--|:--|
| `/lol items [version]` | 装备列表 | `/lol items` `/lol items 14.10` |
| `/lol item <id_or_slug>` | 单个装备 | `/lol item 1001` |

### 🔹 lol spells — 召唤师技能

> PandaScore: `GET /lol/spells` · `GET /lol/spells/{id}`

| 命令 | 说明 | 示例 |
|:--|:--|:--|
| `/lol spells` | 召唤师技能列表 | `/lol spells` |
| `/lol spell <id>` | 单个技能 | `/lol spell 1` |

### 🔹 lol runes — 符文

> PandaScore: `GET /lol/runes` · `GET /lol/runes/{id}` · `GET /lol/runes-reforged` · `GET /lol/runes-reforged/{id}` · `GET /lol/runes-reforged-paths` · `GET /lol/runes-reforged-paths/{id}`

| 命令 | 说明 | 示例 |
|:--|:--|:--|
| `/lol runes` | 符文列表（reforged） | `/lol runes` |
| `/lol rune <id>` | 单个符文详情 | `/lol rune 5001` |
| `/lol runes paths` | 符文系列表 | `/lol runes paths` |
| `/lol runes path <id>` | 单个符文系详情 | `/lol runes path 8100` |

### 🔹 lol masteries — 天赋

> PandaScore: `GET /lol/masteries` · `GET /lol/masteries/{id}`

| 命令 | 说明 | 示例 |
|:--|:--|:--|
| `/lol masteries` | 天赋列表 | `/lol masteries` |

### 🔹 lol leagues — 联赛

> PandaScore: `GET /lol/leagues`

| 命令 | 说明 | 示例 |
|:--|:--|:--|
| （联赛信息已内置在赛程/排名/战队等命令中） | | |

### 🔹 哔哩哔哩 / 微博

| 命令 | 说明 | 示例 |
|:--|:--|:--|
| `/lol bilibili` | 多账号 B 站综合动态（哔哩哔哩英雄联盟赛事、英雄联盟赛事、BLG电子竞技俱乐部） | `/lol bilibili` |
| `/lol weibo` | 英雄联盟赛事微博赛前海报最新 5 条 | `/lol weibo` |

### 🔹 订阅 & 管理

| 命令 | 说明 |
|:--|:--|
| `/lol subscribe` | 订阅自动推送（赛程 / B站 / 微博海报） |
| `/lol unsubscribe` | 取消当前会话的自动推送 |
| `/lol apikey` | 查看当前 API Key 状态 |
| `/lol apikey <新Key>` | 手动设置自定义 API Key（可选） |
| `/lol test [season]` | 运行连通性测试 |
| `/lol help` | 显示完整帮助 |

---

### 🌍 支持的赛区

| 命令缩写 | 赛区 | 联赛 Slug |
|:--|:--|:--|
| `lck` | LCK（韩国） | `lol-lck` |
| `lpl` | LPL（中国） | `lol-lpl` |
| `lec` | LEC（欧洲） | `lol-lec` |
| `lcs` | LCS（北美） | `lol-lcs` |
| `lco` | LCO（大洋洲） | `lol-lco` |
| `lcl` | LCL（独联体） | `lol-lcl` |
| `ljl` | LJL（日本） | `lol-ljl` |
| `pcs` | PCS（太平洋） | `lol-pcs` |
| `vcs` | VCS（越南） | `lol-vcs` |
| `cblol` | CBLOL（巴西） | `lol-cblol` |
| `lla` | LLA（拉丁美洲） | `lol-lla` |
| `tcl` | TCL（土耳其） | `lol-tcl` |
| `msi` | MSI 季中邀请赛 | `lol-msi` |
| `worlds` | 全球总决赛 | `lol-worlds` |

> **stage** 参数可选 `regular`（常规赛，默认）或 `playoff`（季后赛）。
> **season** 参数可选 `current`（当前赛季，默认）或具体赛季 ID。

---

### 📡 消息来源集成

| 来源 | 账号 | 功能 | 触发方式 |
|:--|:--|:--|:--|
| 🔔 哔哩哔哩 | 哔哩哔哩英雄联盟赛事 (UID 50329118) | 视频 + 图文动态 + 直播推送 | 订阅自动 / `/lol bilibili` |
| 🔔 哔哩哔哩 | 英雄联盟赛事 (UID 108532523) | 视频 + 图文动态 + 直播推送 | 订阅自动 / `/lol bilibili` |
| 🔔 哔哩哔哩 | BLG电子竞技俱乐部 (UID 268999208) | 视频 + 图文动态 + 直播推送 | 订阅自动 / `/lol bilibili` |
| 📰 微博 | 英雄联盟赛事 (UID 6537214902) | LPL 赛前海报推送 | 订阅自动 / `/lol weibo` |

---

## ⚙️ 插件配置（可选）

以下配置在 AstrBot 插件管理面板中设置，均已有合理默认值，无需修改即可使用：

### 图片渲染

| 配置项 | 类型 | 默认值 | 说明 |
|:--|:--|:--|:--|
| `enable_image_render` | `bool` | `false` | 开启 HTML 图片渲染模式（需 Pillow） |

### API Key

插件内置 PandaScore 和 citoapi 的 API Key，开箱即用：

| 配置项 | 类型 | 默认值 | 说明 |
|:--|:--|:--|:--|
| `cito_api_key` | `string` | `""` | 自定义 citoapi Key。留空则使用内置 Key。也可设环境变量 `CITO_API_KEY` |

> PandaScore 的 API Key 已内置在代码中，无需额外配置。

### B站

3 个账号，每种内容类型独立开关：

| 账号 | UID | 默认推送 |
|:--|:--|:--|
| 哔哩哔哩英雄联盟赛事 | 50329118 | 视频 ✅ · 图文 ✅ · 直播 ❌ |
| 英雄联盟赛事 | 108532523 | 视频 ❌ · 图文 ✅ · 直播 ❌ |
| BLG电子竞技俱乐部 | 268999208 | 视频 ✅ · 图文 ✅ · 直播 ❌ |

| 配置项 | 类型 | 默认值 | 说明 |
|:--|:--|:--|:--|
| `bilibili_push_lol_video` | `bool` | `true` | 哔哩哔哩英雄联盟赛事 — 视频推送 |
| `bilibili_push_lol_article` | `bool` | `true` | 哔哩哔哩英雄联盟赛事 — 图文推送 |
| `bilibili_push_lol_live` | `bool` | `false` | 哔哩哔哩英雄联盟赛事 — 直播推送 |
| `bilibili_push_lolesports_video` | `bool` | `false` | 英雄联盟赛事 — 视频推送 |
| `bilibili_push_lolesports_article` | `bool` | `true` | 英雄联盟赛事 — 图文推送 |
| `bilibili_push_lolesports_live` | `bool` | `false` | 英雄联盟赛事 — 直播推送 |
| `bilibili_push_blg_video` | `bool` | `true` | BLG电子竞技俱乐部 — 视频推送 |
| `bilibili_push_blg_article` | `bool` | `true` | BLG电子竞技俱乐部 — 图文推送 |
| `bilibili_push_blg_live` | `bool` | `false` | BLG电子竞技俱乐部 — 直播推送 |

> B站 Cookie 已硬编码在 `bilibili.py` 中（`_DEFAULT_COOKIE`），也可通过环境变量 `BILIBILI_COOKIE` 覆盖。无需在 WebUI 中配置。

### 微博

| 配置项 | 类型 | 默认值 | 说明 |
|:--|:--|:--|:--|
| `weibo_uids` | `list` | `["6537214902"]` | 微博监控账号 UID 列表 |
| `enable_weibo_poster_push` | `bool` | `true` | 推送赛前海报 |
| `weibo_check_interval` | `int` | `300` | 微博检查间隔（秒） |

---

## 🏗 项目结构

```
astrbot_plugin_lol_notifier/
├── main.py                     # AstrBot 插件入口（16 条命令）
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
        ├── __init__.py
        ├── config.py           # 配置管理
        ├── models.py           # 数据模型（dataclass）
        ├── image_renderer.py   # HTML → 图片渲染
        ├── scheduler.py        # 后台推送调度
        ├── state.py            # 推送去重状态管理
        ├── utils.py            # 工具函数
        ├── fetcher/            # 数据抓取层
        │   ├── __init__.py          # 导出 30+ 个 api 函数 + B站/微博抓取器
        │   ├── api.py               # 数据访问封装（PandaScore 优先 + citoapi 回退 + TTL 缓存）
        │   ├── pandascore.py        # PandaScore HTTP 客户端（主数据源，Bearer Token）
        │   ├── lolesports.py        # citoapi HTTP 客户端（备用数据源，x-api-key）
        │   ├── bilibili.py          # B站 API
        │   ├── bilibili_dynamic.py  # B站动态 API
        │   └── weibo.py             # 微博 API
        └── formatter/          # 格式化层（19 个活跃 formatter）
            ├── __init__.py
            └── message.py
```

### 数据流

```
用户命令 (/lol xxx)
    ↓
main.py → LoLNotifierPlugin（命令解析 & 路由）
    ↓
fetcher/api.py → 数据访问层（league 校验 + TTL 缓存 + Result 封装）
    ↓                        ↓
fetcher/pandascore.py      fetcher/lolesports.py
（主数据源，Bearer Token）   （备用回退，x-api-key）
    ↓                        ↓
PandaScore API              citoapi API
    ↓
formatter/message.py → 格式化输出（文本 / 图片）
    ↓
image_renderer.py → HTML 模板渲染（可选图片模式）
    ↓
AstrBot 消息通道（QQ / Telegram / WebChat）
```

### 架构分层

| 层 | 职责 | 关键模块 |
|:--|:--|:--|
| **命令层** | 解析用户指令，参数校验，结果分发 | `main.py` |
| **数据访问层** | TTL 缓存、league 校验、PandaScore 优先 + citoapi 回退 | `fetcher/api.py` |
| **网络层** | HTTP 请求、速率限制、指数退避（429） | `fetcher/pandascore.py`（主） + `fetcher/lolesports.py`（备） |
| **格式化层** | 将数据转为可读消息 | `formatter/message.py` |
| **渲染层** | HTML 模板 → Pillow 图片渲染 | `image_renderer.py` |
| **调度层** | 定时推送赛程/B站/微博更新 | `scheduler.py` |

---

## 🧪 测试

详见 [TEST.md](./TEST.md)，包含全端点连通性测试、按类别逐类测试、Python 脚本测试、命令清单及错误处理验证。

---

## ⚠️ 已知限制 (Known Limitations)

### 数据源架构

| 层级 | 数据源 | 覆盖范围 |
|:--|:--|:--|
| **主数据源** | [PandaScore](https://pandascore.co) | 赛程、实时比分、积分榜、联赛、系列赛、锦标赛、战队、选手、统计数据、游戏数据（英雄/装备/符文/技能） |
| **备用数据源** | [citoapi](https://api.citoapi.com/api/v1) | 赛程、实时比分、积分榜、比赛结果/详情（仅当 PandaScore 不可用时回退） |

### 功能状态一览

| 功能 | 状态 | 数据源 | 说明 |
|:--|:--|:--|:--|
| 赛程查询 (schedule/next/today) | ✅ 正常 | PandaScore → citoapi | 覆盖 LCK/LPL 等 14 个赛区，支持无赛程时自动跨赛区回退 |
| 实时比赛 (live) | ✅ 正常 | PandaScore → citoapi | 需要比赛正在进行中 |
| 比赛结果/详情 (result/detail) | ✅ 正常 | PandaScore → citoapi | 自动获取详细对局数据 |
| 积分榜 (standings) | ✅ 正常 | PandaScore → citoapi | 赛季进行中数据更完整 |
| 对局事件/帧 (game events/frames) | ✅ 正常 | PandaScore | 对局内详细事件与时间轴帧数据 |
| 战队信息 (team info) | ✅ 正常 | PandaScore | 支持名称直接模糊匹配 |
| 战队统计 (team stats) | ✅ 正常 | PandaScore | 赛季统计数据 |
| 选手列表/信息 (players/player) | ✅ 正常 | PandaScore | 依赖 PandaScore 选手数据库覆盖 |
| 选手统计 (player stats) | ✅ 正常 | PandaScore | 赛季统计数据 |
| 系列赛 (series) | ✅ 正常 | PandaScore | 支持按赛区和状态筛选 |
| 锦标赛 (tournaments) | ✅ 正常 | PandaScore | 支持按赛区和状态筛选 |
| 英雄/装备/符文/技能 | ✅ 正常 | PandaScore | 参考数据，无回退 |
| 比赛选手统计 (match stats) | ✅ 正常 | PandaScore | 单场比赛的选手数据 |
| B站动态 | ✅ 正常 | B站 API | 三个账号独立内容类型开关 |
| 微博海报 | ✅ 正常 | 微博 API | 英雄联盟赛事赛前海报 |

### 已知局限性

- **PandaScore 速率限制**：PandaScore API 有请求频率限制，短时间内大量请求可能触发限流，插件已内置速率控制和 TTL 缓存以缓解
- **非活跃赛季**：休赛期 standings/stats 等数据可能返回空
- **实时数据**：`/lol live` 仅在有正在进行的官方比赛时可获取
- **选手覆盖**：PandaScore 的选手数据库对非顶级联赛的覆盖可能不完整
- **参考数据**：英雄/装备/符文/技能等参考数据仅依赖 PandaScore，无备用数据源
- **citoapi 回退**：当 PandaScore 不可用时自动回退到 citoapi，但 citoapi 仅覆盖核心赛程/比分/积分榜功能

---

## 📊 功能状态

所有功能以 **PandaScore 为主数据源**，citoapi 作为赛程/比分/积分榜的备用回退。以下状态基于实际命令集。

### 赛程 & 比赛

| 命令 | 数据源 | 状态 | 备注 |
|:--|:--|:--|:--|
| `/lol schedule` | PandaScore → citoapi | ✅ 正常 | 完整赛程查询，按距今天最近排序（默认 LPL，最近 5 场） |
| `/lol next` | PandaScore → citoapi | ✅ 正常 | 下一场未开赛的完整时间表 |
| `/lol today` | PandaScore → citoapi | ✅ 正常 | 今日所有赛程 |
| `/lol live` | PandaScore → citoapi | ✅ 正常 | 正在进行的实时比赛（击杀/经济/塔/龙） |
| `/lol result` | PandaScore → citoapi | ✅ 正常 | 比赛结果（默认最近一场） |
| `/lol detail` | PandaScore → citoapi | ✅ 正常 | 比赛完整详情（含对局数据） |
| `/lol standings` | PandaScore → citoapi | ✅ 正常 | 积分榜 / 排名 |

### 对局 & 比赛扩展

| 命令 | 数据源 | 状态 | 备注 |
|:--|:--|:--|:--|
| `/lol game info <id>` | PandaScore | ✅ 正常 | 单局详情 |
| `/lol game events <id>` | PandaScore | ✅ 正常 | 对局事件（击杀/推塔/打龙等） |
| `/lol game frames <id>` | PandaScore | ✅ 正常 | 对局帧数据（时间轴） |
| `/lol match games <id>` | PandaScore | ✅ 正常 | 比赛所有对局 |
| `/lol match stats <id>` | PandaScore | ✅ 正常 | 比赛选手统计 |

### 战队 & 选手

| 命令 | 数据源 | 状态 | 备注 |
|:--|:--|:--|:--|
| `/lol team info [name]` | PandaScore | ✅ 正常 | 查看所有战队或按名称模糊筛选 |
| `/lol team stats <id>` | PandaScore | ✅ 正常 | 战队赛季统计 |
| `/lol players [league]` | PandaScore | ✅ 正常 | 选手列表 |
| `/lol player <id>` | PandaScore | ✅ 正常 | 选手信息 |
| `/lol player stats <id>` | PandaScore | ✅ 正常 | 选手赛季统计 |

### 系列赛 & 锦标赛

| 命令 | 数据源 | 状态 | 备注 |
|:--|:--|:--|:--|
| `/lol series [league] [status]` | PandaScore | ✅ 正常 | 系列赛列表（status: past/running/upcoming） |
| `/lol series detail <id>` | PandaScore | ✅ 正常 | 系列赛详情 |
| `/lol tournaments [league] [status]` | PandaScore | ✅ 正常 | 锦标赛列表 |
| `/lol tournament <id>` | PandaScore | ✅ 正常 | 锦标赛详情 |

### 参考数据（游戏静态数据）

| 命令 | 数据源 | 状态 | 备注 |
|:--|:--|:--|:--|
| `/lol champions [version]` | PandaScore | ✅ 正常 | 英雄列表 |
| `/lol champion <id_or_slug>` | PandaScore | ✅ 正常 | 单个英雄详情 |
| `/lol items [version]` | PandaScore | ✅ 正常 | 装备列表 |
| `/lol item <id_or_slug>` | PandaScore | ✅ 正常 | 单个装备详情 |
| `/lol spells` | PandaScore | ✅ 正常 | 召唤师技能列表 |
| `/lol spell <id>` | PandaScore | ✅ 正常 | 单个技能详情 |
| `/lol runes` | PandaScore | ✅ 正常 | 符文列表（reforged） |
| `/lol rune <id>` | PandaScore | ✅ 正常 | 单个符文详情 |
| `/lol runes paths` | PandaScore | ✅ 正常 | 符文系列表 |
| `/lol runes path <id>` | PandaScore | ✅ 正常 | 单个符文系详情 |
| `/lol masteries` | PandaScore | ✅ 正常 | 天赋列表 |

### 第三方平台

| 命令 | 数据源 | 状态 | 备注 |
|:--|:--|:--|:--|
| `/lol bilibili` | B站 API | ✅ 正常 | 三个 B 站账号综合动态（视频/图文/直播） |
| `/lol weibo` | 微博 API | ✅ 正常 | 英雄联盟赛事微博赛前海报 |

## 📝 License

MIT © [MareDevi](https://github.com/MareDevi)
