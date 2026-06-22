# 🧪 citoapi 端点测试文档

本文件列出所有 citoapi 端点对应的测试用例，用于验证 LoL plugin 数据抓取功能的正确性。

---

## 前置条件

- 插件已安装并运行在 AstrBot 中
- citoapi Key 可用（内置 Key 或已配置 `CITO_API_KEY` 环境变量）
- 测试命令在 AstrBot 支持的聊天平台发送（如 QQ/Telegram/WebChat）

---

## 1. 赛程查询 — `GET /lol/leagues/{slug}/schedule`

### 命令

```
/lol schedule lck
/lol schedule lpl
/lol schedule lec
/lol schedule lcs
/lol schedule msi
/lol schedule worlds
```

### 预期结果

| 检查项 | 预期 |
|:--|:--|
| 返回格式 | 赛程列表，含日期/时间/对阵/BO 等字段 |
| 空赛区 | 提示"不支持的赛区: xxx" |
| 支持赛区 | LCK / LPL / LEC / LCS / LCO / LCL / LJL / PCS / VCS / CBLOL / LLA / TCL / MSI / Worlds |

### 验证点

- [ ] 赛程数据正常返回
- [ ] 时间正确（本地时区）
- [ ] 对阵双方队名正确
- [ ] BO 类型正确（BO1/BO3/BO5）

---

## 2. 实时比赛 — `GET /lol/live`

### 命令

```
/lol live
```

### 预期结果

| 检查项 | 预期 |
|:--|:--|
| 无比赛时 | "没有正在进行的比赛" |
| 有比赛时 | 显示实时比分、经济、击杀、塔、龙、男爵、局比分 |
| 实时帧 | 每局 `game_id` 从 `/lol/live/games/{gameId}/window` 获取 |

### 验证点

- [ ] 实时帧数据正确（击杀/经济/塔/龙/男爵）
- [ ] 多局比赛并行显示（如 BO3/BO5）
- [ ] 赛区筛选正常：`/lol live lck`

---

## 3. 实时帧 — `GET /lol/live/games/{gameId}/window`

### 间接测试（通过 `/lol live`）

实时帧通过 `/lol live` 命令间接测试。如需直接测试，修改 `lolesports.py` 中的 `fetch_live_frame` 打印日志。

### 验证点

- [ ] `fetch_live_frame()` 正确返回 `LiveGameFrame`
- [ ] `gameState`、`blueTeam`、`redTeam` 字段非空
- [ ] `totalKills`、`totalGold`、`towers`、`barons`、`drakes`、`inhibitors` 为有效数字

---

## 4. 排名/积分榜 — `GET /lol/leagues/{slug}/standings`

### 命令

```
/lol standings lck
/lol standings lpl
```

### 预期结果

| 检查项 | 预期 |
|:--|:--|
| 返回格式 | 排名列表，含排名/队名/胜/负/积分 |
| 数据完整性 | 所有队伍均有排名和战绩 |

### 验证点

- [ ] 排名列表正确
- [ ] 胜场数/负场数正确
- [ ] 积分正确

---

## 5. 比赛详情（含 BP） — `GET /lol/matches/{matchId}`

### 命令

```
/lol detail <match_id>
/lol bp <match_id>
```

### 预期结果

| 检查项 | 预期 |
|:--|:--|
| 返回格式 | 比赛详情，含每局 BP 阵容 |
| BP 数据 | 蓝方/红方 Ban/Pick 完整列表 |
| 无效 ID | 返回错误提示 |

### 验证点

- [ ] 比赛详情正常返回（联赛/阶段/对阵/场次）
- [ ] BP 阵容数据正确（Ban×5 + Pick×5 per side per game）
- [ ] 每局胜负标记正确
- [ ] 无效 match_id 返回错误提示

---

## 6. API Key 管理

### 命令

```
/lol apikey
/lol apikey cito_new_test_key
```

### 预期结果

| 检查项 | 预期 |
|:--|:--|
| 查看状态 | 显示 Key 掩码 + 来源（内置/环境变量/手动） |
| 设置新 Key | 显示"✅ citoapi Key 已更新" |
| 无效 Key | 设置不报错（验证在下次请求时进行） |

### 验证点

- [ ] Key 掩码只显示前 8 位 + `****` + 后 4 位
- [ ] 环境变量 `CITO_API_KEY` 优先级最高
- [ ] 手动设置后 Key 立即生效

---

## 7. 错误处理

### 模拟场景

| 场景 | 测试方法 | 预期行为 |
|:--|:--|:--|
| 网络断开 | 断开网络后查询 | 提示"网络请求异常" |
| HTTP 403 | 设置无效 Key | 提示"API Key 无效" |
| HTTP 429 | 高频请求 | 提示"请求频率过高" |
| HTTP 5xx | 服务器错误 | 提示"citoapi 服务器错误" |
| 不支持赛区 | `/lol schedule xyz` | 提示"不支持的赛区: xyz" |

---

## 测试清单

```
□ 赛程查询 — LCK/LPL/LEC/LCS/MSI/Worlds
□ 实时比赛 — 比赛进行中时
□ 实时帧   — 数据完整性
□ 排名     — LCK/LPL 正确
□ 比赛详情 — 含 BP
□ API Key  — 查看/设置/环境变量
□ 错误处理 — 网络/403/429/5xx/无效赛区
□ 14 赛区支持 — 全部 slug 映射正确
```

---

## 测试日志

| 日期 | 测试项 | 结果 | 备注 |
|:--|:--|:--|:--|
| - | - | - | - |
