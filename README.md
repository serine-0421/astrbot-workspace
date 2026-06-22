# 🎮 AstrBot LoL Notifier

LoL 电竞赛事推送与查询插件，覆盖 **LCK / LPL / LEC / LCS / MSI / Worlds** 等 14 个赛区，提供赛程、实时比分、BP 阵容、积分榜、战队/选手详情、英雄统计、全球战力排行、转会动态等一站式查询。同时集成 B 站官号视频监控、BLG 战队 BP 图文推送、微博赛前海报抓取。

> 💡 **开箱即用** — 插件内置 API Key，安装后直接使用，无需额外配置。

---

## 📦 安装

```bash
cd AstrBot/data/plugins
git clone https://github.com/MareDevi/astrbot_plugin_lol_notifier.git
```

依赖：`httpx`、`aiohttp`、`pillow`

---

## 📖 命令参考

所有命令以 `/lol` 开头。`[ ]` 表示可选参数，`< >` 表示必填参数。

### 🔹 赛程 & 比赛

| 命令 | 说明 | 示例 |
|:--|:--|:--|
| `/lol schedule [赛区] [regular\|playoff]` | 查询赛区完整赛程（默认最近 5 场） | `/lol schedule lpl` |
| `/lol next [赛区]` | 下一场比赛的完整时间表 | `/lol next lck` |
| `/lol today [赛区]` | 今日所有赛程 | `/lol today` `/lol today lpl` |
| `/lol week [赛区]` | 本周所有赛程 | `/lol week` `/lol week lck` |
| `/lol live [赛区]` | 正在进行的实时比赛（击杀/经济/塔/龙） | `/lol live` `/lol live lck` |
| `/lol result [赛区] [round]` | 比赛结果（默认最近一场，可指定场次） | `/lol result lpl` `/lol result lck 3` |
| `/lol bp [赛区] [round]` | 比赛 BP 阵容（默认最近一场） | `/lol bp lck` `/lol bp lpl 2` |
| `/lol detail [赛区] [round]` | 比赛完整详情（含对局数据） | `/lol detail lck` |
| `/lol standings [赛区]` | 积分榜 / 排名 | `/lol standings lck` `/lol standings lpl` |

### 🔹 战队 — `/lol team`

| 子命令 | 说明 | 示例 |
|:--|:--|:--|
| `search <关键词>` | 搜索战队（获取战队 ID） | `/lol team search BLG` |
| `info <战队ID>` | 战队详细信息 | `/lol team info BLG` |
| `roster <战队ID>` | 当前阵容列表 | `/lol team roster BLG` |
| `matches <战队ID>` | 近期比赛记录 | `/lol team matches BLG` |
| `stats <战队ID>` | 赛季统计数据 | `/lol team stats BLG` |
| `h2h <战队A> <战队B>` | 两队历史交手记录 | `/lol team h2h BLG TES` |

### 🔹 选手 — `/lol player`

| 子命令 | 说明 | 示例 |
|:--|:--|:--|
| `search <关键词>` | 搜索选手（获取选手 ID） | `/lol player search Faker` |
| `info <选手ID>` | 选手详细信息 | `/lol player info Faker` |
| `stats <选手ID>` | 赛季统计数据 | `/lol player stats Faker` |
| `champions <选手ID>` | 英雄池 & 使用率 | `/lol player champions Faker` |

### 🔹 锦标赛 — `/lol tournament`

| 子命令 | 说明 | 示例 |
|:--|:--|:--|
| `info <锦标赛ID>` | 锦标赛详情 | `/lol tournament info worlds2025` |
| `standings <锦标赛ID>` | 锦标赛积分榜 | `/lol tournament standings worlds2025` |
| `bracket <锦标赛ID>` | 淘汰赛对阵图 | `/lol tournament bracket worlds2025` |
| `mvp <锦标赛ID>` | 锦标赛 MVP | `/lol tournament mvp worlds2025` |

### 🔹 英雄数据 — `/lol champion`

| 子命令 | 说明 | 示例 |
|:--|:--|:--|
| `stats [赛区]` | 英雄胜率/登场率/禁用率统计 | `/lol champion stats lck` |
| `presence [赛区]` | 英雄 Pick / Ban 率排行 | `/lol champion presence lpl` |

### 🔹 排名 & 排行榜

| 命令 | 说明 | 示例 |
|:--|:--|:--|
| `/lol ranking gpr` | 全球战力排名 (GPR) | `/lol ranking gpr` |
| `/lol ranking players <指标>` | 选手数据排名 | `/lol ranking players kda` |
| `/lol leaderboard <指标> [赛区]` | 赛区内数据排行榜 | `/lol leaderboard kda lck` |

**排行榜指标：** `kda` `kills` `deaths` `assists` `cs` `gold` `vision` `damage`

**选手排名指标：** `kda` `kills` `deaths` `assists` `cs`

### 🔹 其他查询

| 命令 | 说明 | 示例 |
|:--|:--|:--|
| `/lol trending` | 热门趋势概览（选手/战队/英雄） | `/lol trending` |
| `/lol history <worlds\|msi>` | 世界赛 / MSI 历史冠军 | `/lol history worlds` |
| `/lol transfers [赛区]` | 转会动态 | `/lol transfers lck` |
| `/lol records [赛区]` | 赛事历史记录 | `/lol records` |

### 🔹 订阅 & 管理

| 命令 | 说明 |
|:--|:--|
| `/lol subscribe` | 订阅自动推送（赛程/B站视频/微博海报） |
| `/lol unsubscribe` | 取消当前会话的自动推送 |
| `/lol apikey` | 查看当前 API Key 状态 |
| `/lol apikey <新Key>` | 手动设置自定义 API Key（可选） |
| `/lol test` | 运行连通性测试 |
| `/lol help` | 显示完整帮助 |

---

### 🌍 支持的赛区

| 缩写 | 赛区 | citoapi Slug |
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

---

### 📡 消息来源集成

| 来源 | 功能 | 触发方式 |
|:--|:--|:--|
| 🔔 B站 LOL 官号 | 官方视频投稿推送 | 订阅后自动 |
| 🔵 B站 BLG 官号 | BP 图文动态推送 | 订阅后自动 |
| 📰 微博 | LPL 赛前海报推送 | 订阅后自动 |

---

## ⚙️ 插件配置（可选）

以下配置在 AstrBot 插件管理面板中设置，均已有合理默认值，无需修改即可使用：

| 配置项 | 默认值 | 说明 |
|:--|:--|:--|
| `enable_image_render` | `false` | 开启 HTML 图片渲染模式 |
| `enable_match_notifications` | `true` | 启用赛事自动推送 |
| `enable_bilibili_video_push` | `true` | 推送 B站 LOL 官号视频 |
| `enable_bilibili_blg_bp_push` | `true` | 推送 BLG BP 动态 |
| `enable_weibo_poster_push` | `true` | 推送微博赛前海报 |

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
        ├── __init__.py
        ├── config.py           # 配置管理
        ├── models.py           # 数据模型
        ├── image_renderer.py   # HTML → 图片
        ├── scheduler.py        # 后台推送调度
        ├── state.py            # 去重状态管理
        ├── utils.py            # 工具函数
        ├── fetcher/            # 数据抓取层
        │   ├── api.py               # 数据访问封装
        │   ├── lolesports.py        # citoapi 网络层
        │   ├── bilibili.py          # B站 API
        │   ├── bilibili_dynamic.py  # B站动态 API
        │   └── weibo.py             # 微博 API
        └── formatter/          # 格式化层
            ├── card.py         # 卡片格式化
            └── message.py      # 消息格式化
```

### 数据流

```
用户命令 (/lol xxx)
    ↓
main.py → LoLNotifierPlugin（命令解析 & 路由）
    ↓
api.py → 数据访问层（league 校验、数据过滤）
    ↓
lolesports.py → citoapi HTTP 请求
    ↓
citoapi (https://api.citoapi.com/api/v1)
    ↓
message.py → 格式化输出（文本/图片）
    ↓
AstrBot 消息通道（QQ / Telegram / WebChat）
```

---

## 🧪 测试

详见 [TEST.md](./TEST.md)，包含全端点连通性测试、按类别逐类测试、Python 脚本测试、命令清单及错误处理验证。

---

## ❓ FAQ

**Q: 支持哪些赛区？**
A: 14 个：LCK、LPL、LEC、LCS、LCO、LCL、LJL、PCS、VCS、CBLOL、LLA、TCL、MSI、Worlds。

**Q: 需要配置 API Key 吗？**
A: 不需要。插件内置了可用 Key，安装即用。如果想用自己的 Key 获得更稳定服务，可通过 `/lol apikey <你的key>` 设置。

**Q: `/lol live` 返回"没有正在进行的比赛"？**
A: 仅在比赛进行中才有实时数据。请确认当前是否有 League 正在比赛。

**Q: 如何获取战队/选手 ID？**
A: 使用 `/lol team search <关键词>` 或 `/lol player search <关键词>` 即可获取 ID，再用于 info/stats 等命令。

**Q: 只想自动推送，不想手动查？**
A: 执行 `/lol subscribe`，调度器在后台自动推送赛程、B站视频和微博海报，无需主动查询。

**Q: 数据来源可靠吗？**
A: 赛事数据来自 citoapi (`https://api.citoapi.com/api/v1`)，B站/微博来自平台公开接口。

---

## 📝 License

MIT © [MareDevi](https://github.com/MareDevi)
