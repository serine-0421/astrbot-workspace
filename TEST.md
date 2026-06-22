# 🧪 LoL Notifier 本地测试文档

> citoapi 全端点连通性验证 + AstrBot 命令测试 + Python 脚本测试

## 前置条件

```powershell
cd E:\serine\dev\astrbot-workspace
.\.venv\Scripts\Activate.ps1
python -c "import httpx; print('httpx OK')"
```

---

## 一、全端点连通性验证

保存为 `test_citoapi.py`，运行后检查各端点 HTTP 状态：

```python
"""citoapi 全端点连通性测试"""
import asyncio
import httpx

BASE = "https://api.citoapi.com/api/v1"
KEY = "cito_dc5cfcfa4b9aca180e71c0e1282be83ef2bfc7658b9658ee5c88813fb6163091"
HEADERS = {"x-api-key": KEY, "User-Agent": "Mozilla/5.0"}

ENDPOINTS = [
    # Leagues
    "/lol/leagues",
    "/lol/leagues/lol-lck",
    # Schedule
    "/lol/leagues/lol-lck/schedule",
    "/lol/schedule/upcoming",
    "/lol/schedule/completed",
    "/lol/schedule/today",
    "/lol/schedule/week",
    # Live
    "/lol/live",
    # Teams
    "/lol/teams",
    # Players
    "/lol/players",
    # Tournaments
    "/lol/tournaments",
    # Standings
    "/lol/leagues/lol-lck/standings",
    "/lol/standings?league=lol-lck",
    # Champions
    "/lol/champions/stats",
    "/lol/champions/presence",
    # Rankings
    "/lol/rankings/gpr",
    "/lol/rankings/players?metric=kda",
    "/lol/rankings/teams?metric=wins",
    # History
    "/lol/history/worlds",
    "/lol/history/msi",
    # Transfers
    "/lol/transfers",
    # Leaderboards
    "/lol/leaderboards/kda",
    "/lol/leaderboards/kills",
    "/lol/leaderboards/deaths",
    "/lol/leaderboards/assists",
    "/lol/leaderboards/cs",
    "/lol/leaderboards/gold",
    "/lol/leaderboards/vision",
    "/lol/leaderboards/damage",
    # Trending
    "/lol/trending",
    "/lol/trending/players",
    "/lol/trending/teams",
    "/lol/trending/champions",
    # Static Data
    "/lol/static/champions",
    "/lol/static/items",
    "/lol/static/runes",
    "/lol/static/summonerspells",
    "/lol/static/patches",
    # Regions
    "/lol/regions",
    # Records
    "/lol/records",
    "/lol/records/milestones",
    # Awards
    "/lol/awards",
    "/lol/awards/mvp",
    "/lol/allstar",
    "/lol/playoffs",
]


async def test_one(client: httpx.AsyncClient, path: str) -> tuple[str, int | str]:
    url = f"{BASE}{path}"
    try:
        r = await client.get(url, timeout=20)
        return (path, r.status_code)
    except Exception as e:
        return (path, f"ERR: {e}")


async def main():
    async with httpx.AsyncClient(headers=HEADERS, timeout=20) as cli:
        tasks = [test_one(cli, p) for p in ENDPOINTS]
        results = await asyncio.gather(*tasks)

    ok = sum(1 for _, sc in results if isinstance(sc, int) and 200 <= sc < 300)
    fail = sum(1 for _, sc in results if isinstance(sc, int) and not (200 <= sc < 300))
    err = sum(1 for _, sc in results if isinstance(sc, str))

    print(f"\n{'='*60}")
    print(f"  总计: {len(results)}  通过: {ok}  失败: {fail}  异常: {err}")
    print(f"{'='*60}")

    for path, sc in results:
        if isinstance(sc, int) and 200 <= sc < 300:
            print(f"  ✅ {path}")
        elif isinstance(sc, str):
            print(f"  ❌ {path}  →  {sc}")
        else:
            print(f"  ⚠️  {path}  →  HTTP {sc}")

asyncio.run(main())
```

```powershell
python test_citoapi.py
```

预期：大部 HTTP 200 ✅；少数需 ID 参数的端点返回 400/404 属于正常。

---

## 二、按类别逐类测试

### 2.1 Leagues
```
GET /lol/leagues              → 全部联赛
GET /lol/leagues/lol-lck      → LCK 详情
```

### 2.2 Schedule
```
GET /lol/leagues/lol-lck/schedule          → LCK 赛程
GET /lol/schedule/today                    → 今日
GET /lol/schedule/week                     → 本周
GET /lol/schedule/upcoming?league=lol-lck  → 即将到来
GET /lol/schedule/completed?league=lol-lck → 已完成
```

### 2.3 Live
```
GET /lol/live                        → 实时比赛列表
GET /lol/live/games/{id}/window      → 实时帧（击杀/经济）
GET /lol/live/games/{id}/stats       → 实时统计
GET /lol/live/games/{id}/timeline    → 时间线
GET /lol/live/games/{id}/events      → 事件流
```

### 2.4 Teams
```
GET /lol/teams                      → 全部
GET /lol/teams?league=lol-lck       → 按联赛过滤
GET /lol/teams/{id}                 → 单个
GET /lol/teams/{id}/roster          → 阵容
GET /lol/teams/{id}/matches         → 近期比赛
GET /lol/teams/{id}/stats           → 统计
GET /lol/teams/{id}/h2h/{other}     → 交手记录
GET /lol/teams/{id}/champions       → 英雄使用统计
```

### 2.5 Players
```
GET /lol/players                    → 全部
GET /lol/players?league=lol-lck     → 按联赛
GET /lol/players/{id}               → 单个
GET /lol/players/{id}/stats         → 统计
GET /lol/players/{id}/career        → 生涯
GET /lol/players/{id}/champions     → 英雄池
GET /lol/players/{id}/matches       → 近期比赛
```

### 2.6 Tournaments
```
GET /lol/tournaments                 → 全部
GET /lol/tournaments/{id}           → 单个
GET /lol/tournaments/{id}/standings → 积分榜
GET /lol/tournaments/{id}/bracket   → 淘汰赛对阵
GET /lol/tournaments/{id}/matches   → 比赛列表
GET /lol/tournaments/{id}/mvp       → MVP
GET /lol/tournaments/{id}/leaderboards → 排行榜
```

### 2.7 Standings/Champions/Rankings/Leaderboards
参见 `src/astrbot_plugin_lol_notifier/fetcher/lolesports.py` 中所有函数。

---

## 三、Python 脚本测试（无需 AstrBot）

```python
"""直接调用 fetcher API 层"""
import asyncio, sys
sys.path.insert(0, "src")

from astrbot_plugin_lol_notifier.fetcher.api import (
    get_schedule, get_standings, get_today_schedule,
    get_all_teams, get_gpr, get_leaderboard,
    get_trending, get_transfers,
)
from astrbot_plugin_lol_notifier.models import Success, Failure

async def test():
    tests = [
        ("schedule",  get_schedule("lck")),
        ("standings", get_standings("lck")),
        ("today",     get_today_schedule()),
        ("teams",     get_all_teams("lck")),
        ("gpr",       get_gpr()),
        ("ldb-kda",   get_leaderboard("kda", "lck")),
        ("trending",  get_trending()),
        ("transfers", get_transfers("lck")),
    ]
    for name, coro in tests:
        r = await coro
        ok = isinstance(r, Success)
        if ok and r.value:
            d = f"({len(r.value)}条)" if isinstance(r.value, list) else \
                f"(keys:{list(r.value)[:3]})" if isinstance(r.value, dict) else str(r.value)[:40]
        else:
            d = r.error[:60] if isinstance(r, Failure) else ""
        print(f"{'✅' if ok else '❌'} {name:12} {d}")

asyncio.run(test())
```

---

## 四、AstrBot 命令测试清单

### 比赛查询
```
□ /lol schedule lck          □ /lol schedule lpl
□ /lol next lck              □ /lol live / live lck
□ /lol result                □ /lol bp lck
□ /lol detail                □ /lol standings lck
□ /lol today                 □ /lol week
```

### 战队 / 选手 / 锦标赛
```
□ /lol team search T1        □ /lol team roster {id}
□ /lol team matches {id}     □ /lol team h2h T1 GEN
□ /lol player search Faker   □ /lol player stats {id}
□ /lol player champions {id} □ /lol tournament info {id}
□ /lol tournament bracket {id}  □ /lol tournament mvp {id}
```

### 数据查询
```
□ /lol champion stats lck    □ /lol champion presence lck
□ /lol ranking gpr           □ /lol ranking players kda
□ /lol leaderboard kda lck   □ /lol leaderboard kills lck
□ /lol trending              □ /lol history worlds
□ /lol transfers lck         □ /lol records
```

### 管理
```
□ /lol subscribe             □ /lol unsubscribe
□ /lol apikey                □ /lol test
```

---

## 五、错误处理

| 场景 | 预期 |
|:--|:--|
| 无效 Key | 下次查询提示 Key 无效 |
| 不支持赛区 | `/lol schedule xyz` → 提示 14 个可用赛区 |
| 无效指标 | `/lol leaderboard foobar` → 提示 8 个可用指标 |
| 缺参数 | `/lol team info` → 提示需要战队 ID |

---

## 六、常见问题

| 症状 | 原因 | 解决 |
|:--|:--|:--|
| 全部 401 | Key 无效 | `/lol apikey` 检查 |
| 部分 404 | ID 参数错误 | 先用 search 获取正确 ID |
| 实时为空 | 当前无比赛 | 正常现象 |
| league 报错 | slug 格式错误 | 用小写 `lck` 而非 `LCK` |
| 超时 | 网络 / citoapi 在境外 | 检查代理
