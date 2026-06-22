"""AstrBot plugin: LoL Notifier

Provides LoL esports push notifications and on-demand query commands.

Commands (prefix /lol):
    /lol help
    /lol schedule [league] [regular|playoff] [season]
    /lol next [league] [regular|playoff] [season]
    /lol live [league]
    /lol result [league] [regular|playoff] [round]
    /lol bp [league] [regular|playoff] [round]
    /lol detail [league] [regular|playoff] [round]
    /lol standings [league] [regular|playoff] [season]
    /lol subscribe
    /lol unsubscribe
    /lol apikey [key]        查看/设置 citoapi Key 状态
    /lol test [season]

League: lck lpl lec lcs lco lcl ljl pcs vcs cblol lla tcl msi worlds
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

from .src.astrbot_plugin_lol_notifier.fetcher import api
from .src.astrbot_plugin_lol_notifier.fetcher.lolesports import get_api_key, set_api_key
from .src.astrbot_plugin_lol_notifier import formatter as fmt
from .src.astrbot_plugin_lol_notifier import image_renderer as img
from .src.astrbot_plugin_lol_notifier.models import Failure, Success
from .src.astrbot_plugin_lol_notifier.scheduler import LoLScheduler

HELP_TEXT = """🎮 LoL Notifier 指令列表

查询命令：
  /lol schedule [league] [regular|playoff] [season]
      近期赛程（默认最近 5 场，按赛区与赛段筛选）
  /lol next [league] [regular|playoff] [season]
      下一场完整时间表
  /lol live [league]
      正在进行的实时比赛（击杀/经济/塔/龙/男爵）
  /lol result [league] [regular|playoff] [round]
      比赛结果（默认最近一场）
  /lol bp [league] [regular|playoff] [round]
      单局 BP（默认最近一场）
  /lol detail [league] [regular|playoff] [round]
      比赛详细信息（默认最近一场）
  /lol standings [league] [regular|playoff] [season]
      排名 / 积分榜

  可用赛区: lck lpl lec lcs lco lcl ljl pcs vcs cblol lla tcl msi worlds

管理命令：
  /lol subscribe     订阅当前会话的自动推送
  /lol unsubscribe   取消当前会话的自动推送
  /lol apikey [key|refresh]  查看/设置 Key、强制刷新
  /lol test [season]        测试插件各项查询功能

已实现的自动推送（订阅后自动触发）：
  📺 B站 LOL官号 (50329118)    → 最新视频投稿
  🔵 B站 BLG官号 (545271146)   → BP 图文动态
  📢 微博各队官号              → LPL 赛前海报（LPL+预告关键词）

赛事推送框架（待接入数据源）：
  ⏰ 距比赛日 ≤ 24小时  →  当日赛程 + 对阵表 + 双方战队海报
  🔍 比赛前 30 分钟     →  首发名单 + 历史交手 + 赛前预测
  🧠 每小局 BP 结束后   →  格式化阵容名单
  📊 每小局结束后       →  简要胜负 + 比赛战报
  🏆 比赛结束后         →  最终比分 + MVP/FMVP + B站回放
  🏅 淘汰赛关键节点     →  晋级/淘汰情况 + 后续对阵
"""


@register(
    "astrbot_plugin_lol_notifier",
    "MareDevi",
    "LoL赛事推送与查询插件",
    "1.1.3",
    "https://github.com/MareDevi/astrbot_plugin_lol_notifier",
)
class LoLNotifierPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig) -> None:
        super().__init__(context)
        self.config = config
        self.scheduler = LoLScheduler(self, context, config)

    @property
    def _image_mode(self) -> bool:
        return bool(self.config.get("enable_image_render", False))

    async def _render_or_text(self, event: AstrMessageEvent, text: str, image_path: str):
        """Yield image result if image mode is on, otherwise plain text."""
        if self._image_mode:
            try:
                return event.image_result(image_path)
            except Exception as exc:
                logger.warning(f"[LoLNotifier] Image render failed, fallback to text: {exc}")
        return event.plain_result(text)

    async def _render_query_result(
        self,
        event: AstrMessageEvent,
        result,
        *,
        has_payload,
        render_text,
        render_image,
        empty_text: str,
        error_prefix: str,
    ):
        match result:
            case Success(value=value) if has_payload(value):
                text = render_text(value)
                image_path = await render_image(value)
                yield await self._render_or_text(event, text, image_path)
            case Success():
                yield event.plain_result(empty_text)
            case Failure(error=err):
                logger.error(f"[LoLNotifier] {error_prefix}: {err}")
                yield event.plain_result(f"❌ {err}")

    async def initialize(self) -> None:
        """Initialize plugin and start scheduler."""
        key = get_api_key()
        masked = key[:8] + "****" + key[-4:] if len(key) > 12 else "****"
        logger.info(f"[LoLNotifier] citoapi Key: {masked}")

        self.scheduler.start()
        logger.info("[LoLNotifier] Plugin initialized.")

    async def terminate(self) -> None:
        """Stop the scheduler and close HTTP session."""
        await self.scheduler.stop()
        await api.close_session()
        logger.info("[LoLNotifier] Plugin terminated.")

    # ──────────────────── command_group ────────────────────────────
    @filter.command_group("lol")
    def lol(self) -> None:
        """LoL 赛事查询与推送"""

    # ──────────────────── sub-commands ─────────────────────────────

    @lol.command("help")
    async def lol_help(self, event: AstrMessageEvent):
        """显示帮助信息"""
        yield event.plain_result(HELP_TEXT)

    @lol.command("schedule")
    async def lol_schedule(
        self,
        event: AstrMessageEvent,
        league: str = "lck",
        stage: str = "regular",
        season: str = "current",
    ):
        """查看赛程（LCK / LPL，常规赛 / 淘汰赛）"""
        result = await api.get_schedule(league, stage, season)
        async for message in self._render_query_result(
            event,
            result,
            has_payload=lambda value: bool(value),
            render_text=lambda value: fmt.format_schedule(value),
            render_image=lambda value: img.render_schedule(value),
            empty_text="⏳ 暂未找到可显示的赛程信息，请稍后再试。",
            error_prefix="/lol schedule error",
        ):
            yield message

    @lol.command("next")
    async def lol_next(
        self,
        event: AstrMessageEvent,
        league: str = "lck",
        stage: str = "regular",
        season: str = "current",
    ):
        """查看下一场完整时间表"""
        result = await api.get_schedule(league, stage, season)
        match result:
            case Success(value=schedule) if schedule:
                next_match = schedule[0]
                text = fmt.format_schedule([next_match], limit=1)
                image_path = await img.render_schedule([next_match], limit=1)
                yield await self._render_or_text(event, text, image_path)
            case Success():
                yield event.plain_result("📅 当前没有可显示的下一场赛程。")
            case Failure(error=err):
                logger.error(f"[LoLNotifier] /lol next error: {err}")
                yield event.plain_result(f"❌ 获取下一场赛程失败：{err}")

    @lol.command("live")
    async def lol_live(
        self,
        event: AstrMessageEvent,
        league: str = "",
    ):
        """查看正在进行的实时比赛（击杀/经济/塔/龙/男爵）"""
        from .src.astrbot_plugin_lol_notifier.fetcher.lolesports import (
            fetch_live_match_details,
            fetch_live_matches,
        )
        from .src.astrbot_plugin_lol_notifier.formatter.message import (
            format_live_match,
        )

        league_arg = (league or "").strip().lower() or None
        result = await fetch_live_matches(league=league_arg)

        match result:
            case Success(value=live_matches) if live_matches:
                # 获取详细帧数据
                detailed = []
                for lm in live_matches:
                    detailed.append(await fetch_live_match_details(lm))

                # 格式化输出
                lines_parts = []
                for lm in detailed:
                    lines_parts.append(format_live_match(lm))
                yield event.plain_result("\n\n".join(lines_parts))
            case Success():
                yield event.plain_result("📡 当前没有正在进行的比赛。")
            case Failure(error=err):
                logger.error(f"[LoLNotifier] /lol live error: {err}")
                yield event.plain_result(f"❌ 获取实时比赛数据失败：{err}")

    @lol.command("result")
    async def lol_result(
        self,
        event: AstrMessageEvent,
        league: str = "lck",
        stage: str = "regular",
        round_num: str = "last",
    ):
        """查看比赛结果，可指定场次 round"""
        round_arg: int | str = int(round_num) if round_num.isdigit() else "last"
        result = await api.get_match_result(league, stage, round_arg)
        async for message in self._render_query_result(
            event,
            result,
            has_payload=lambda value: bool(value.games),
            render_text=lambda value: fmt.format_match_result(value),
            render_image=lambda value: img.render_match_result(value),
            empty_text="⏳ 比赛结果暂未公布，请比赛结束后再试。",
            error_prefix="/lol result error",
        ):
            yield message

    @lol.command("bp")
    async def lol_bp(
        self,
        event: AstrMessageEvent,
        league: str = "lck",
        stage: str = "regular",
        round_num: str = "last",
    ):
        """查看单局 BP，可指定场次 round"""
        round_arg: int | str = int(round_num) if round_num.isdigit() else "last"
        result = await api.get_match_bp(league, stage, round_arg)
        async for message in self._render_query_result(
            event,
            result,
            has_payload=lambda value: bool(value.games),
            render_text=lambda value: fmt.format_match_bp(value),
            render_image=lambda value: img.render_match_bp(value),
            empty_text="⏳ BP 数据暂未公布，请稍后再试。",
            error_prefix="/lol bp error",
        ):
            yield message

    @lol.command("detail")
    async def lol_detail(
        self,
        event: AstrMessageEvent,
        league: str = "lck",
        stage: str = "regular",
        round_num: str = "last",
    ):
        """查看比赛详细信息，可指定场次 round"""
        round_arg: int | str = int(round_num) if round_num.isdigit() else "last"
        result = await api.get_match_detail(league, stage, round_arg)
        async for message in self._render_query_result(
            event,
            result,
            has_payload=lambda value: bool(value.games),
            render_text=lambda value: fmt.format_match_detail(value),
            render_image=lambda value: img.render_match_detail(value),
            empty_text="⏳ 比赛详细信息暂未公布，请稍后再试。",
            error_prefix="/lol detail error",
        ):
            yield message

    @lol.command("standings")
    async def lol_standings(
        self,
        event: AstrMessageEvent,
        league: str = "lck",
        stage: str = "regular",
        season: str = "current",
    ):
        """查看排名 / 积分榜"""
        result = await api.get_standings(league, stage, season)
        async for message in self._render_query_result(
            event,
            result,
            has_payload=lambda value: bool(value),
            render_text=lambda value: fmt.format_standings(value),
            render_image=lambda value: img.render_standings(value),
            empty_text="⏳ 暂未找到可显示的排名/积分榜，请稍后再试。",
            error_prefix="/lol standings error",
        ):
            yield message

    @lol.command("subscribe")
    async def lol_subscribe(self, event: AstrMessageEvent):
        """订阅当前会话的自动推送"""
        session = event.unified_msg_origin
        added = await self.scheduler.add_subscriber(session)
        if added:
            yield event.plain_result(
                f"✅ 已订阅 LoL 自动推送！\n"
                f"当前共 {self.scheduler.subscriber_count()} 个会话已订阅。"
            )
        else:
            yield event.plain_result("ℹ️ 当前会话已经订阅过了。发送 /lol unsubscribe 可以取消。")

    @lol.command("unsubscribe")
    async def lol_unsubscribe(self, event: AstrMessageEvent):
        """取消当前会话的自动推送"""
        session = event.unified_msg_origin
        removed = await self.scheduler.remove_subscriber(session)
        if removed:
            yield event.plain_result("✅ 已取消订阅 LoL 自动推送。")
        else:
            yield event.plain_result("ℹ️ 当前会话尚未订阅。发送 /lol subscribe 可以订阅。")

    @lol.command("apikey")
    async def lol_apikey(
        self,
        event: AstrMessageEvent,
        key: str = "",
    ):
        """查看/设置 citoapi Key 状态。

        /lol apikey                    查看 Key 状态
        /lol apikey <your-key>         手动设置 Key
        """
        arg = key.strip()

        if arg:
            set_api_key(arg)
            new_key = get_api_key()
            masked = new_key[:8] + "****" + new_key[-4:] if len(new_key) > 12 else "****"
            yield event.plain_result(f"✅ citoapi Key 已更新: {masked}")
            return

        current = get_api_key()
        masked = current[:8] + "****" + current[-4:] if len(current) > 12 else "****"
        import os
        source = (
            "环境变量 CITO_API_KEY" if os.environ.get("CITO_API_KEY", "").strip()
            else "手动设置" if current != "cito_dc5cfcfa4b9aca180e71c0e1282be83ef2bfc7658b9658ee5c88813fb6163091"
            else "内置 Key"
        )
        yield event.plain_result(
            f"🔑 citoapi Key 状态\n\n"
            f"  Key: {masked}\n"
            f"  来源: {source}\n"
            f"  citoapi Key 长期有效，无需刷新\n\n"
            f"💡 设置新 Key: /lol apikey <你的key>\n"
            f"💡 环境变量: CITO_API_KEY"
        )

    @lol.command("test")
    async def lol_test(self, event: AstrMessageEvent, season: str = "current"):
        """测试插件各项查询功能"""
        year = season if season else "current"
        yield event.plain_result(f"🔧 正在测试 {year} 赛季数据，请稍候...")

        async def run(name: str, coro) -> tuple[str, bool, str]:
            r = await coro
            match r:
                case Success(value=val):
                    if isinstance(val, list):
                        return (name, True, f"✅ {len(val)} 条记录")
                    label = getattr(val, "match_name", None) or getattr(
                        val, "league", None
                    ) or getattr(val, "stage", None)
                    return (name, True, f"✅ {label or ''}")
                case Failure(error=err):
                    return (name, False, f"❌ {err}")
            return (name, False, "❌ unknown")

        results: list[tuple[str, bool, str]] = list(
            await asyncio.gather(
                run("赛程(LCK)", api.get_schedule("lck", "regular", year)),
                run("赛程(LPL)", api.get_schedule("lpl", "regular", year)),
                run("赛程(LEC)", api.get_schedule("lec", "regular", year)),
                run("实时比赛", api.get_match_result("lck", "regular", "last")),
                run("BP", api.get_match_bp("lpl", "regular", "last")),
                run("详细信息", api.get_match_detail("lpl", "regular", "last")),
                run("积分/排名", api.get_standings("lck", "regular", year)),
            )
        )

        lines = [f"📋 LoL 插件测试报告 ({year})\n"]
        passed = sum(1 for _, ok, _ in results if ok)
        for name, ok, detail in results:
            lines.append(f"  {'✅' if ok else '❌'} {name}: {detail}")
        lines.append(f"\n共 {passed}/{len(results)} 项通过")
        yield event.plain_result("\n".join(lines))
