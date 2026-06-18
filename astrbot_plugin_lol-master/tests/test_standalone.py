"""独立终端测试脚本 — 无需 AstrBot 框架，直接测试 LoL 数据查询。

用法：
    cd astrbot_plugin_lol-master
    python tests/test_standalone.py          # 测试全部
    python tests/test_standalone.py live     # 仅实时比赛
    python tests/test_standalone.py schedule # 仅赛程
    python tests/test_standalone.py standings # 仅排名

依赖: pip install httpx
"""

from __future__ import annotations

import asyncio
import sys
import time
# ── 修复 Windows 终端 emoji 乱码 ──
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
# ── 路径设置：添加 src 到 sys.path ──
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


async def test_schedule() -> None:
    """测试赛程查询 LCK + LPL"""
    from astrbot_plugin_lol_notifier.fetcher.lolesports import fetch_schedule

    print("\n" + "=" * 60)
    print("📅 赛程查询测试")
    print("=" * 60)

    for league in ("lck", "lpl"):
        t0 = time.monotonic()
        result = await fetch_schedule(league=league)
        elapsed = time.monotonic() - t0

        if result.ok and result.value:
            matches = result.value
            print(f"\n✅ {league.upper()} — {len(matches)} 场比赛 ({elapsed:.1f}s)")
            for m in matches[:3]:
                print(f"   [{m.start_date} {m.start_time}] {m.match_name}  ({m.status})")
            if len(matches) > 3:
                print(f"   ... 还有 {len(matches) - 3} 场")
        elif result.ok:
            print(f"\n⚠️ {league.upper()} — 无赛程数据")
        else:
            print(f"\n❌ {league.upper()} — {result.error}")


async def test_live() -> None:
    """测试实时比赛查询"""
    from astrbot_plugin_lol_notifier.fetcher.lolesports import (
        fetch_live_match_details,
        fetch_live_matches,
    )
    from astrbot_plugin_lol_notifier.formatter.message import format_live_match

    print("\n" + "=" * 60)
    print("📡 实时比赛测试")
    print("=" * 60)

    t0 = time.monotonic()
    result = await fetch_live_matches()
    elapsed = time.monotonic() - t0

    if result.ok and result.value:
        matches = result.value
        print(f"\n✅ 正在进行 {len(matches)} 场比赛 ({elapsed:.1f}s)")

        for lm in matches:
            print(f"\n── [{lm.league_name}] {lm.match_name}  ({lm.score}) {lm.bo_type} ──")

            # 获取详细帧数据
            await fetch_live_match_details(lm)
            print(format_live_match(lm))
    elif result.ok:
        print("\n📡 当前没有正在进行的比赛。")
    else:
        print(f"\n❌ {result.error}")


async def test_standings() -> None:
    """测试排名查询"""
    from astrbot_plugin_lol_notifier.fetcher.lolesports import fetch_standings

    print("\n" + "=" * 60)
    print("📊 排名/积分榜测试")
    print("=" * 60)

    for league in ("lck", "lpl"):
        t0 = time.monotonic()
        result = await fetch_standings(league=league)
        elapsed = time.monotonic() - t0

        if result.ok and result.value:
            entries = result.value
            print(f"\n✅ {league.upper()} — {len(entries)} 支队伍 ({elapsed:.1f}s)")
            for e in entries[:5]:
                print(f"   {e.rank:>2}. {e.team_name:<15} {e.wins}W-{e.losses}L")
            if len(entries) > 5:
                print(f"   ... 还有 {len(entries) - 5} 支")
        elif result.ok:
            print(f"\n⚠️ {league.upper()} — 无排名数据")
        else:
            print(f"\n❌ {league.upper()} — {result.error}")


async def test_match_detail() -> None:
    """测试比赛详情/BP 查询（取赛程第一场已完成比赛）"""
    from astrbot_plugin_lol_notifier.fetcher.lolesports import fetch_match_detail, fetch_schedule

    print("\n" + "=" * 60)
    print("🧠 比赛详情/BP 测试")
    print("=" * 60)

    for league in ("lck", "lpl"):
        sched = await fetch_schedule(league=league)
        if not sched.ok or not sched.value:
            print(f"\n❌ {league.upper()} — 无赛程数据")
            continue

        completed = [m for m in sched.value if m.status in ("completed", "finished")]
        if not completed:
            print(f"\n⚠️ {league.upper()} — 无已完成比赛")
            continue

        target = completed[-1]
        t0 = time.monotonic()
        detail = await fetch_match_detail(target.round)
        elapsed = time.monotonic() - t0

        if detail:
            print(f"\n✅ {league.upper()} — {detail.match_name} ({elapsed:.1f}s)")
            for g in detail.games:
                print(f"   Game {g.game_no}: {g.blue_team} vs {g.red_team} → {g.winner}")
                bp_count = len(getattr(g, "bp", []))
                if bp_count:
                    print(f"      BP: {bp_count} 条 ban/pick 记录")
        else:
            print(f"\n❌ {league.upper()} — 无法获取详情")


async def test_formatter() -> None:
    """测试格式化函数"""
    from astrbot_plugin_lol_notifier.formatter.message import (
        format_live_game_frame,
        format_live_list,
        format_live_match,
    )
    from astrbot_plugin_lol_notifier.models import LiveGameFrame, LiveMatch

    print("\n" + "=" * 60)
    print("🎨 格式化函数测试 (本地模拟数据)")
    print("=" * 60)

    # 模拟 LiveGameFrame
    frame = LiveGameFrame(
        game_id="test-1",
        game_no=1,
        state="in_progress",
        blue_team="T1",
        red_team="GEN",
        blue_kills=12, red_kills=8,
        blue_gold=54000, red_gold=48000,
        blue_towers=5, red_towers=4,
        blue_barons=2, red_barons=1,
        blue_drakes=3, red_drakes=1,
        blue_inhibitors=1, red_inhibitors=0,
        game_time="28:45",
    )
    print("\n── format_live_game_frame ──")
    print(format_live_game_frame(frame))

    # 模拟 LiveMatch
    live = LiveMatch(
        match_id="test",
        league="lck", league_name="LCK",
        match_name="T1 vs GEN",
        teams=["T1", "GEN"],
        score="1:1",
        bo_type="BO3",
        status="in_progress",
        games=[frame],
    )
    print("\n── format_live_match ──")
    print(format_live_match(live))

    print("\n── format_live_list ──")
    print(format_live_list([live]))
    print("\n✅ 格式化函数测试通过")


async def test_models() -> None:
    """测试数据模型"""
    from astrbot_plugin_lol_notifier.models import (
        Failure,
        LeagueMatch,
        LiveGameFrame,
        LiveMatch,
        MatchGame,
        StandingEntry,
        Success,
    )

    print("\n" + "=" * 60)
    print("📦 模型导入测试")
    print("=" * 60)

    s = Success(value="hello")
    assert s.ok and s.value == "hello", "Success failed"
    print("✅ Success<T>")

    f = Failure(error="test error")
    assert not f.ok and f.error == "test error", "Failure failed"
    print("✅ Failure")

    lm = LeagueMatch(league="LCK", match_name="T1 vs GEN", bo_type="BO5")
    assert lm.bo_type == "BO5", "LeagueMatch failed"
    print("✅ LeagueMatch")

    mg = MatchGame(game_no=1, blue_team="T1", red_team="GEN", winner="T1", duration="32:15")
    assert mg.winner == "T1", "MatchGame failed"
    print("✅ MatchGame")

    se = StandingEntry(rank=1, team_name="T1", wins=10, losses=2, points=10)
    assert se.rank == 1, "StandingEntry failed"
    print("✅ StandingEntry")

    lgf = LiveGameFrame(game_id="test", blue_kills=15, red_kills=7, game_time="25:00")
    assert lgf.blue_kills == 15, "LiveGameFrame failed"
    print("✅ LiveGameFrame")

    lvm = LiveMatch(match_id="m1", league_name="LCK", score="2:1")
    assert lvm.score == "2:1", "LiveMatch failed"
    print("✅ LiveMatch")

    print("\n🎉 所有模型测试通过")


# ── 主入口 ──

async def main() -> None:
    print("🎮 LoL Notifier — 独立查询测试")
    print(f"   时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    target = sys.argv[1] if len(sys.argv) > 1 else "all"

    # 模型测试始终运行
    await test_models()

    if target in ("all", "schedule"):
        await test_schedule()

    if target in ("all", "live"):
        await test_live()

    if target in ("all", "standings"):
        await test_standings()

    if target in ("all", "detail", "bp"):
        await test_match_detail()

    if target in ("all", "format"):
        await test_formatter()

    print("\n" + "=" * 60)
    print("🏁 测试完成")

if __name__ == "__main__":
    asyncio.run(main())
