# 🎮 AstrBot LoL Notifier

LoL 电竞赛事推送与查询插件，支持 **LCK / LPL / LEC / LCS / MSI / Worlds** 等 14 个赛区。赛程、比赛结果、BP、实时比分、排名等数据通过 citoapi 获取。集成 B 站官号视频监控、BLG 战队 BP 图文推送、微博赛前海报抓取。

---

## ✨ 功能

### ✅ 已实现

| 功能 | 说明 | 触发方式 |
|:--|:--|:--|
| 📅 赛程查询 | 查看近期比赛安排，按赛区/赛段筛选 | `/lol schedule` |
| ⏭ 下一场比赛 | 下一场即将开始的完整时间表 | `/lol next` |
| 📡 实时比赛 | 正在进行的比赛（击杀/经济/塔/龙/男爵） | `/lol live` |
| 🏆 比赛结果 | 已完成比赛的结果 | `/lol result` |
| 🧠 BP 阵容 | 每局 Ban/Pick 详情 | `/lol bp` |
| 📋 比赛详情 | 完整比赛信息 | `/lol detail` |
| 📊 排名/积分榜 | 常规赛/淘汰赛排名 | `/lol standings` |
| 📢 自动推送 | 订阅后自动推送通知 | `/lol subscribe` |
| 🔔 B站 LOL 官号 | 官方视频投稿推送 | 自动（订阅后） |
| 🔵 B站 BLG 官号 | BP 图文动态推送 | 自动（订阅后） |
| 📰 微博海报 | LPL 赛前海报推送 | 自动（订阅后） |
| 🔑 API Key 管理 | 查看/设置 citoapi Key | `/lol apikey` |

### 🔜 规划中 / 框架已就绪

| 功能 | 状态 | 说明 |
|:--|:--|:--|
| ⏰ 距比赛日 ≤ 24h | 🚧 调度器已实现 | 当日赛程 + 对阵表 + 战队海报 |
| 🔍 赛前 30 分钟 | 🚧 调度器已实现 | 首发名单 + 历史交手 + 赛前预测 |
| 🧠 BP 结束自动推送 | 🚧 调度器已实现 | 自动推送阵容名单 |
| 📊 每局结束自动推送 | 🚧 调度器已实现 | 胜负 + 文字战报 |
| 🏆 比赛结束自动推送 | 🚧 调度器已实现 | 最终比分 + MVP/FMVP + B站回放 |
| 🏅 淘汰赛关键节点 | 🚧 调度器已实现 | 晋级/淘汰 + 后续对阵 |

> 赛事推送框架已在后台调度器中实现。当前第三方平台数据（B站/微博）可正常推送，比赛数据自动推送依赖 citoapi 接入后即可激活。

---

## 📦 安装

```bash
cd AstrBot/data/plugins
git clone https://github.com/MareDevi/astrbot_plugin_lol_notifier.git
```

依赖：
- `httpx` - HTTP 请求
- `aiohttp` - 异步 HTTP

---

## 🔑 API Key 配置（必读）

LoL Esports 赛事数据（赛程/排名/比赛详情/Ban-Pick/实时比分）通过 **citoapi** 获取。

### 获取 Key

citoapi Key **长期有效，无需刷新**。详见 [citoapi 文档](https://api.citoapi.com/)。

### 配置方式（任选一种）

**方式 1：环境变量（推荐）**

```bash
# Windows PowerShell
$env:CITO_API_KEY = "cito_xxxxxxxx"

# Linux / macOS
export CITO_API_KEY="cito_xxxxxxxx"
```

**方式 2：插件配置文件**

在 AstrBot 插件配置中添加：
```json
{ "cito_api_key": "cito_xxxxxxxx" }
```

**方式 3：命令行动态设置**

```
/lol apikey cito_xxxxxxxx
```

> 💡 插件内置了一个默认 Key，不配置也可直接使用。但建议配置自己的 Key 以获得更稳定的服务。

### 检查 Key 状态

```
/lol apikey
```

输出示例：
```
🔑 citoapi Key 状态

  Key: cito_dc5****3091
  来源: 内置 Key
  citoapi Key 长期有效，无需刷新

💡 设置新 Key: /lol apikey <你的key>
💡 环境变量: CITO_API_KEY
```

---

## 📖 命令参考

### 赛程查询

```
/lol schedule [lck|lpl] [regular|playoff] [season]
```

| 示例 | 说明 |
|:--|:--|
| `/lol schedule` | LCK 常规赛赛程（默认） |
| `/lol schedule lck regular` | LCK 常规赛赛程 |
| `/lol schedule lpl playoff` | LPL 淘汰赛赛程 |
| `/lol schedule lck regular 2024` | 2024 赛季 LCK 常规赛 |

### 下一场比赛

```
/lol next [lck|lpl] [regular|playoff] [season]
```

| 示例 | 说明 |
|:--|:--|
| `/lol next` | LCK 下一场比赛 |
| `/lol next lpl playoff` | LPL 淘汰赛下一场 |

### 实时比赛（击杀/经济/塔/龙/男爵）

```
/lol live [lck|lpl]
```

| 示例 | 说明 |
|:--|:--|
| `/lol live` | 所有正在进行的比赛 |
| `/lol live lck` | 仅 LCK |

输出包含：双方击杀数、经济差、防御塔数、小龙数、大龙数、比赛时间。

### 比赛结果

```
/lol result [lck|lpl] [regular|playoff] [round]
```

| 示例 | 说明 |
|:--|:--|
| `/lol result` | 最近一场比赛结果（默认 LCK） |
| `/lol result lpl` | LPL 最近一场 |
| `/lol result lck playoff` | LCK 淘汰赛最近一场 |

### BP 阵容

```
/lol bp [lck|lpl] [regular|playoff] [round]
```

### 比赛详情

```
/lol detail [lck|lpl] [regular|playoff] [round]
```

### 排名/积分榜

```
/lol standings [lck|lpl] [regular|playoff] [season]
```

| 示例 | 说明 |
|:--|:--|
| `/lol standings` | LCK 常规赛排名 |
| `/lol standings lpl playoff` | LPL 淘汰赛排名 |

### 订阅管理

```
/lol subscribe      订阅当前会话的自动推送
/lol unsubscribe    取消订阅
```

### API Key 管理

```
/lol apikey             查看 Key 状态
/lol apikey <你的key>   手动设置 Key
```

### 测试

```
/lol test          测试当前赛季各项查询
/lol test 2024     测试 2024 赛季
```

---

## ⚙️ 配置项

| 配置项 | 类型 | 默认值 | 说明 |
|:--|:--|:--|:--|
| `cito_api_key` | str | `""` | citoapi Key（长期有效，无需刷新） |
| `enable_image_render` | bool | `false` | 是否启用 HTML 渲染图片 |
| `enable_match_notifications` | bool | `true` | 是否启用赛事自动推送 |
| `bilibili_uid` | str | `"50329118"` | B站 LOL 官号 UID |
| `enable_bilibili_video_push` | bool | `true` | 是否推送 B站视频更新 |
| `bilibili_blg_uid` | str | `"545271146"` | B站 BLG 官号 UID |
| `enable_bilibili_blg_bp_push` | bool | `true` | 是否推送 BLG BP 动态 |
| `weibo_uids` | list | `["6537214902"]` | 微博号 UID 列表 |
| `weibo_cookie` | str | `""` | 微博 Cookie（部分内容需登录） |
| `enable_weibo_poster_push` | bool | `true` | 是否推送微博海报 |

---

## 🏗 项目结构

```
astrbot_plugin_lol_notifier/
├── main.py                     # AstrBot 插件入口
├── metadata.yaml               # 插件元数据
├── README.md                   # 本文件
├── requirements.txt            # Python 依赖
├── data/                       # 运行时数据
│   └── cmd_config.json         # 指令配置
└── src/
    └── astrbot_plugin_lol_notifier/
        ├── __init__.py
        ├── config.py           # 配置与默认值
        ├── image_renderer.py   # HTML → 图片渲染
        ├── models.py           # 数据模型（dataclass）
        ├── scheduler.py        # 后台推送调度器
        ├── state.py            # 推送去重状态管理
        ├── utils.py            # 工具函数
        ├── fetcher/            # 数据抓取层
        │   ├── __init__.py
        │   ├── api.py               # 数据访问封装
        │   ├── lolesports.py        # citoapi 封装
        │   ├── bilibili.py          # B站 API
        │   ├── bilibili_dynamic.py  # B站动态 API
        │   └── weibo.py             # 微博 API
        └── formatter/          # 格式化层
            ├── __init__.py
            ├── card.py         # 卡片格式化
            └── message.py      # 消息格式化
```

### 数据流

```
用户命令 (/lol xxx)
    ↓
main.py → LoLNotifierPlugin
    ↓
api.py → 数据访问层（校验/过滤/封装）
    ↓
lolesports.py → citoapi 请求封装
    ↓
citoapi (https://api.citoapi.com/api/v1)
```

---

## ❓ FAQ

**Q: 赛程查询返回空或报错？**
A: 首先检查 API Key 状态：`/lol apikey`。citoapi Key 长期有效，如遇问题可尝试设置新 Key。

**Q: `/lol live` 返回"没有正在进行的比赛"？**
A: 仅在比赛进行中时才有实时数据。请确认当前是否有支持的 League 比赛。

**Q: 支持哪些赛区？**
A: 支持 14 个赛区：LCK、LPL、LEC、LCS、LCO、LCL、LJL、PCS、VCS、CBLOL、LLA、TCL、MSI、Worlds。通过 citoapi 的 league slug 映射自动支持。

**Q: 只想要自动推送，不需要指令查询？**
A: 可以。只需执行 `/lol subscribe`，调度器会在后台自动推送，无需主动查询。

**Q: 数据来源是否可靠？**
A: 赛事数据来自 citoapi (`https://api.citoapi.com/api/v1`)，B站/微博数据来自各平台公开接口。

---

## 📝 License

MIT © [MareDevi](https://github.com/MareDevi)
