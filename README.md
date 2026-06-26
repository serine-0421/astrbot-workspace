# 🎮 AstrBot LoL Notifier

LoL 电竞赛事推送与查询插件，覆盖 **LCK / LPL / LEC / LCS / MSI / Worlds** 等 14 个赛区，提供赛程、实时比分、BP 阵容、积分榜、战队/选手详情、英雄统计、全球战力排行、转会动态等一站式查询。同时集成 B 站官号视频监控、BLG 战队 BP 图文推送、微博赛前海报抓取。

> 💡 **开箱即用** — 插件内置 API Key，安装后直接使用，无需额外配置。

---

## 📦 安装

```bash
cd AstrBot/data/plugins
git clone https://github.com/MareDevi/astrbot_plugin_lol_notifier.git
```

依赖：
- [AstrBot](https://github.com/AstrBotDevs/AstrBot) >= 适配当前 API 版本
- `httpx`、`aiohttp`、`pillow`
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
| `search <关键词>` | 搜索战队（支持直接名称匹配） | `/lol team search BLG` |
| `info <战队名>` | 战队完整信息（含阵容+近期比赛+统计） | `/lol team info BLG` |
| `h2h <战队A> <战队B>` | 两队历史交手记录 | `/lol team h2h BLG TES` |

### 🔹 选手 — `/lol player`

| 子命令 | 说明 | 示例 |
|:--|:--|:--|
| `search <关键词>` | 搜索选手（获取选手 ID） | `/lol player search Faker` |
| `info <选手ID>` | 选手详细信息 | `/lol player info Faker` |
| `stats <选手ID>` | 赛季统计数据 | `/lol player stats Faker` |
| `champions <选手ID>` | 英雄池 & 使用率 | `/lol player champions Faker` |

### 🔹 世界赛 — `/lol tournament`

| 子命令 | 说明 | 示例 |
|:--|:--|:--|
| `info <赛事ID>` | 世界赛详情 (⚠️ API 可能不可用) | `/lol tournament info worlds2024` |
| `standings <赛事ID>` | 世界赛积分榜 (⚠️ API 可能不可用) | `/lol tournament standings worlds2024` |
| `bracket <赛事ID>` | 淘汰赛对阵 (⚠️ API 可能不可用) | `/lol tournament bracket worlds2024` |
| `mvp <赛事ID>` | 世界赛 MVP (⚠️ API 可能不可用) | `/lol tournament mvp worlds2024` |

### 🔹 英雄数据 — `/lol champion`

| 子命令 | 说明 | 示例 |
|:--|:--|:--|
| `/lol champion stats [赛区]` | 英雄胜率/登场率/禁用率统计 (⚠️) | `/lol champion stats lck` |
| `/lol champion presence [赛区]` | 英雄 Pick / Ban 率排行 | `/lol champion presence lpl` |

### 🔹 排名 & 排行榜

| 命令 | 说明 | 示例 |
|:--|:--|:--|
| `/lol ranking gpr` | 全球战力排名 (GPR) (⚠️ API 可能不可用) | `/lol ranking gpr` |
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
A: 赛事数据来自 citoapi (`https://api.citoapi.com/api/v1/lol`)，B站/微博来自平台公开接口。

---

## ⚠️ 已知限制 (Known Limitations)

以下功能依赖 citoapi 的特定端点，可能因 API 覆盖范围或不支持而返回空数据：

| 功能 | 状态 | 说明 |
|:--|:--|:--|
| 赛程查询 (schedule/next/today/week) | ✅ 正常 | 覆盖 LCK/LPL 等主要赛区 |
| 实时比赛 (live) | ✅ 正常 | 需要比赛正在进行中 |
| 比赛结果/详情 (result/detail/bp) | ✅ 正常 | 自动获取详细对局数据 |
| 积分榜 (standings) | ✅ 正常 | 赛季进行中数据更完整 |
| 战队信息/阵容 (team info) | ✅ 正常 | 支持名称直接匹配 |
| 战队搜索 (team search) | ⚠️ 部分 | 搜索 API 可能不稳定，支持直接名称回退 |
| 战队交手记录 (team h2h) | ⚠️ 部分 | API 数据可能为空 |
| 选手搜索/信息 (player search/info) | ⚠️ 部分 | 依赖 API 选手数据库覆盖 |
| 世界赛查询 (tournament *) | ⚠️ 部分 | `/lol/tournaments/*` 端点可能在 citoapi 中不可用 |
| 英雄统计 (champion stats) | ⚠️ 部分 | `/lol/champions/stats` 端点可能返回空数据 |
| 英雄 Pick/Ban 率 (champion presence) | ⚠️ 部分 | 同上 |
| 全球战力排名 (ranking gpr) | ⚠️ 部分 | `/lol/rankings/gpr` 端点可能不可用 |
| 热门趋势 (trending) | ⚠️ 部分 | 取决于 API 数据更新频率 |
| 历史赛事 (history) | ⚠️ 部分 | 数据可能不完整或有格式差异 |
| 转会信息 (transfers) | ⚠️ 部分 | 字段名可能与 API 返回不完全匹配 |
| 赛事记录 (records) | ⚠️ 部分 | 同上 |

> 💡 标记为 ⚠️ 的功能取决于 citoapi 的数据覆盖。如果 API 返回空数据，插件会显示相应的提示信息。建议优先使用标记为 ✅ 的稳定功能。

---

## � 功能状态

### 赛程 & 比赛

| 命令 | 状态 | 备注 |
|:--|:--|:--|
| `lol schedule` | ✅ 正常 | 完整赛程查询 |
| `lol next` | ✅ 正常 | 自动区分过去/未来比赛 |
| `lol today` | ✅ 正常 | 今日赛程 |
| `lol week` | ✅ 正常 | 本周赛程 |
| `lol live` | ✅ 正常 | 实时比赛需赛事进行中 |
| `lol result` | ✅ 正常 | 支持 `round` 或 `match_id` 匹配 |
| `lol bp` | ✅ 正常 | 需比赛已完成且 API 有 BP 数据 |
| `lol detail` | ✅ 正常 | 需比赛已完成且有详情 |
| `lol standings` | ✅ 正常 | 多路径数据提取 |

### 战队 (`/lol team`)

| 子命令 | 状态 | 备注 |
|:--|:--|:--|
| `search` | ✅ 正常 | 建议使用英文名，大小写敏感 |
| `info` | ⚠️ 部分 | API 数据覆盖取决于 citoapi |
| `roster` | ✅ 正常 | 修复：角色排序+多字段名匹配 |
| `matches` | ✅ 正常 | 近期比赛记录 |
| `stats` | ✅ 正常 | 赛季统计 |
| `h2h` | ✅ 正常 | 历史交手记录 |

### 选手 (`/lol player`)

| 子命令 | 状态 | 备注 |
|:--|:--|:--|
| `search` | ✅ 正常 | 建议使用英文 ID（如 Faker），大小写敏感 |
| `info` | ⚠️ 部分 | API 数据覆盖取决于 citoapi |
| `stats` | ✅ 正常 | 赛季统计数据 |
| `champions` | ✅ 正常 | 英雄池与使用率 |

### 锦标赛 (`/lol tournament`)

| 子命令 | 状态 | 备注 |
|:--|:--|:--|
| `info` | ✅ 正常 | 已修复：slug 解析+回退 |
| `standings` | ✅ 正常 | slug 回退支持 |
| `bracket` | ✅ 正常 | 淘汰赛对阵图 |
| `mvp` | ✅ 正常 | slug 回退支持 |

### 英雄 & 排行

| 命令 | 状态 | 备注 |
|:--|:--|:--|
| `lol champion stats` | ⚠️ 部分 | 需要对应赛区赛季有数据 |
| `lol champion presence` | ⚠️ 部分 | 仅在活跃赛季有数据 |
| `lol ranking gpr` | ⚠️ 部分 | 依赖 API 是否已发布该期 GPR |
| `lol ranking players` | ✅ 正常 | 选手数据排名 |
| `lol leaderboard` | ✅ 正常 | 赛区内排行榜 |

### 其他查询

| 命令 | 状态 | 备注 |
|:--|:--|:--|
| `lol trending` | ✅ 正常 | 修复：显示具体内容而非仅计数 |
| `lol history` | ⚠️ 部分 | 已增强字段匹配；数据质量取决于 API |
| `lol transfers` | ⚠️ 部分 | 已增强多字段名匹配；数据质量取决于 API |
| `lol records` | ⚠️ 部分 | 历史记录依赖于 API 覆盖 |

### 已知局限性

- **搜索大小写敏感**：`/lol player search Faker` 必须大小写完全匹配 API 中的记录
- **非活跃赛季**：休赛期 standings/stats/champion 可能返回空数据
- **实时数据**：`/lol live` 仅在有正在进行的官方比赛时可获取
- **API 覆盖**：citoapi 对部分赛区/赛季/锦标赛的数据覆盖可能不完整
- **转会数据**：API 返回的数据字段名可能不一致，虽然增加了多字段匹配，部分条目仍可能显示为空

## �📝 License

MIT © [MareDevi](https://github.com/MareDevi)
