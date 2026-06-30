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
    /lol today [league]
    /lol week [league]
    /lol team info [team_name]
    /lol player stats <player_id>
    /lol player earnings <player_id>
    /lol transfers [league]
    /lol transfers-player <player_id>
    /lol transfers-team <team_slug>
    /lol coverage
    /lol subscribe
    /lol unsubscribe
    /lol apikey [key]
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
from .src.astrbot_plugin_lol_notifier.fetcher import bilibili as bili_fetcher
from .src.astrbot_plugin_lol_notifier.fetcher import weibo as weibo_fetcher
from .src.astrbot_plugin_lol_notifier.fetcher.lolesports import get_api_key, set_api_key
from .src.astrbot_plugin_lol_notifier.config import get_weibo_uids
from .src.astrbot_plugin_lol_notifier import formatter as fmt
from .src.astrbot_plugin_lol_notifier import image_renderer as img
from .src.astrbot_plugin_lol_notifier.models import Failure, Success
from .src.astrbot_plugin_lol_notifier.scheduler import LoLScheduler

HELP_TEXT = """🎮 LoL Notifier 指令列表

━━━ 比赛查询 ━━━
  /lol schedule [league] [regular|playoff] [season]
      近期赛程（默认 LPL，最近 5 场）
  /lol next [league] [regular|playoff] [season]
      下一场完整时间表
  /lol live [league]
      正在进行的实时比赛
  /lol result [league] [regular|playoff] [round]
      比赛结果（默认最近一场）
  /lol bp [league] [regular|playoff] [round]
      单局 BP（默认最近一场）
  /lol detail [league] [regular|playoff] [round]
      比赛详细信息
  /lol standings [league] [regular|playoff] [season]
      排名 / 积分榜
  /lol today [league]
      今日赛程
  /lol week [league]
      本周赛程

━━━ 战队 / 选手 ━━━
  /lol team info [name]          战队信息（可按名称筛选）
  /lol player stats <player_id>      选手统计数据
  /lol player earnings <player_id>   选手生涯奖金

━━━ 转会 ━━━
  /lol transfers [league]            赛区转会动态
  /lol transfers-player <player_id>  选手转会历史
  /lol transfers-team <team>         战队转会记录

━━━ B站 / 微博 ━━━
  /lol bilibili                      B站 LOL官号最新 5 条视频
  /lol weibo                         微博赛前海报最新 5 条

━━━ 其他 ━━━
  /lol coverage                      直播覆盖矩阵

━━━ 赛区 ━━━
  lck lpl lec lcs lco lcl ljl pcs vcs cblol lla tcl msi worlds

━━━ 管理 ━━━
  /lol subscribe / unsubscribe / apikey / test"""


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
    @filter.event_message_type(filter.EventMessageType.ALL)
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
        league: str = "lpl",
        stage: str = "regular",
        season: str = "current",
    ):
        """查看赛程。默认 LPL 赛区，可选 stage (regular|playoff)、season。"""
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
        league: str = "lpl",
        stage: str = "regular",
        season: str = "current",
    ):
        """查看下一场完整时间表（仅显示未开始的比赛）。默认 LPL 赛区。"""
        result = await api.get_schedule(league, stage, season)
        match result:
            case Success(value=schedule) if schedule:
                from datetime import datetime
                now = datetime.now().strftime("%Y-%m-%d")
                # 分离：未来的比赛 vs 已过去的比赛
                unstarted = [m for m in schedule if m.status in ("unstarted", "")]
                in_progress = [m for m in schedule if m.status in ("in_progress", "live")]
                
                # 在未开始的比赛中，找日期最近的（最近的未来比赛）
                if unstarted:
                    unstarted.sort(key=lambda m: (m.start_date, m.start_time))
                    next_match = unstarted[0]  # 最近的未来比赛
                    is_past = False
                elif in_progress:
                    next_match = in_progress[0]
                    is_past = False
                else:
                    # 没有未来比赛，尝试回退到其他联赛
                    fallback_result = await self._find_next_in_other_leagues(
                        league, stage, season
                    )
                    if fallback_result is not None:
                        fallback_match, fallback_league = fallback_result
                        fallback_league_upper = fallback_league.upper()
                        text = fmt.format_schedule([fallback_match], limit=1)
                        text = text.replace(
                            "📅 LoL 近期赛程",
                            f"⏭️ 下一场比赛（{league.upper()}暂无未来赛程，最近是 {fallback_league_upper}）",
                        )
                        image_path = await img.render_schedule([fallback_match], limit=1)
                        yield await self._render_or_text(event, text, image_path)
                        return

                    # 没有任何联赛有未来比赛，显示最近一次已完成的
                    completed = [m for m in schedule if m.status in ("completed", "finished")]
                    if completed:
                        completed.sort(key=lambda m: (m.start_date, m.start_time), reverse=True)
                        next_match = completed[0]
                        is_past = True
                    else:
                        sorted_matches = sorted(schedule, key=lambda m: (m.start_date, m.start_time), reverse=True)
                        next_match = sorted_matches[0]
                        is_past = True

                if is_past:
                    # 显示为最近已完成 + 提示没有未来赛程
                    text = fmt.format_schedule([next_match], limit=1)
                    text = text.replace("📅 LoL 近期赛程", "📅 最近一场比赛（暂无未来赛程）")
                else:
                    text = fmt.format_schedule([next_match], limit=1)
                    text = text.replace("📅 LoL 近期赛程", "⏭️ 下一场比赛")
                image_path = await img.render_schedule([next_match], limit=1)
                yield await self._render_or_text(event, text, image_path)
            case Success():
                # 当前赛程为空，尝试回退到其他联赛
                fallback_result = await self._find_next_in_other_leagues(
                    league, stage, season
                )
                if fallback_result is not None:
                    fallback_match, fallback_league = fallback_result
                    fallback_league_upper = fallback_league.upper()
                    text = fmt.format_schedule([fallback_match], limit=1)
                    text = text.replace(
                        "📅 LoL 近期赛程",
                        f"⏭️ 下一场比赛（{league.upper()}暂无赛程，最近是 {fallback_league_upper}）",
                    )
                    image_path = await img.render_schedule([fallback_match], limit=1)
                    yield await self._render_or_text(event, text, image_path)
                    return
                yield event.plain_result("📅 当前没有可显示的赛程信息。")
            case Failure(error=err):
                logger.error(f"[LoLNotifier] /lol next error: {err}")
                yield event.plain_result(f"❌ 获取下一场赛程失败：{err}")

    async def _find_next_in_other_leagues(
        self, original_league: str, stage: str, season: str
    ):
        """在其他联赛中寻找最近的未开始比赛。
        返回 (match, league_name) 或 None。"""
        # 优先顺序：国际赛事 → 主要赛区 → 次要赛区
        _FALLBACK_ORDER = [
            "msi", "worlds", "lck", "lpl", "lec", "lcs",
            "pcs", "vcs", "lco", "ljl", "cblol", "lla", "lcl", "tcl",
        ]
        original_lower = original_league.strip().lower()
        for fallback_league in _FALLBACK_ORDER:
            if fallback_league == original_lower:
                continue
            result = await api.get_schedule(fallback_league, stage, season)
            if result.ok and result.value:
                unstarted = [
                    m for m in result.value
                    if m.status in ("unstarted", "")
                ]
                in_progress = [
                    m for m in result.value
                    if m.status in ("in_progress", "live")
                ]
                if unstarted:
                    unstarted.sort(key=lambda m: (m.start_date, m.start_time))
                    return (unstarted[0], fallback_league)
                if in_progress:
                    return (in_progress[0], fallback_league)
        return None

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

        result = await fetch_live_matches(league if league else None)
        match result:
            case Success(value=detailed) if detailed:
                for lm in detailed:
                    await fetch_live_match_details(lm)
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
        league: str = "lpl",
        stage: str = "regular",
        round_num: str = "last",
    ):
        """查看比赛结果，可指定场次 round"""
        round_arg: int | str = int(round_num) if round_num.isdigit() else "last"
        # 优先走 detail 路径（包含 games 数据）
        detail_result = await api.get_match_detail(league, stage, round_arg)
        if detail_result.ok and detail_result.value:
            if detail_result.value.games:
                async for message in self._render_query_result(
                    event,
                    detail_result,
                    has_payload=lambda value: bool(value.games),
                    render_text=lambda value: fmt.format_match_detail(value),
                    render_image=lambda value: img.render_match_detail(value),
                    empty_text="⏳ 比赛结果暂未公布，请比赛结束后再试。",
                    error_prefix="/lol result error",
                ):
                    yield message
                return
            # 有 match 但没有 games → 回退显示基本信息
        # 回退到 schedule 路径（只显示基本信息）
        result = await api.get_match_result(league, stage, round_arg)
        async for message in self._render_query_result(
            event,
            result,
            has_payload=lambda value: value is not None,
            render_text=lambda value: fmt.format_match_basic(value),
            render_image=lambda value: img.render_match_result(value),
            empty_text="⏳ 比赛结果暂未公布，请比赛结束后再试。",
            error_prefix="/lol result error",
        ):
            yield message

    @lol.command("bp")
    async def lol_bp(
        self,
        event: AstrMessageEvent,
        league: str = "lpl",
        stage: str = "regular",
        round_num: str = "last",
    ):
        """查看比赛BP/详情，可指定场次 round"""
        round_arg: int | str = int(round_num) if round_num.isdigit() else "last"
        result = await api.get_match_detail(league, stage, round_arg)
        if result.ok and result.value and result.value.games:
            async for message in self._render_query_result(
                event,
                result,
                has_payload=lambda value: bool(value.games),
                render_text=lambda value: fmt.format_match_bp(value),
                render_image=lambda value: img.render_match_bp(value),
                empty_text="⏳ 比赛数据暂未公布，请稍后再试。",
                error_prefix="/lol bp error",
            ):
                yield message
            return
        # 回退：显示基本信息
        basic = await api.get_match_result(league, stage, round_arg)
        if basic.ok and basic.value:
            yield event.plain_result(fmt.format_match_basic(basic.value))
            return
        async for message in self._render_query_result(
            event,
            Success(value=None),
            has_payload=lambda value: False,
            render_text=lambda value: "",
            render_image=lambda value: "",
            empty_text="⏳ 比赛数据暂未公布，请稍后再试。",
            error_prefix="/lol bp error",
        ):
            yield message

    @lol.command("detail")
    async def lol_detail(
        self,
        event: AstrMessageEvent,
        league: str = "lpl",
        stage: str = "regular",
        round_num: str = "last",
    ):
        """查看比赛详细信息，可指定场次 round 或直接 match_id"""
        round_arg: int | str = int(round_num) if round_num.isdigit() else "last"
        result = await api.get_match_detail(league, stage, round_arg)
        if result.ok and result.value:
            if result.value.games:
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
                return
            # 有 match 但没有 games → 回退显示基本信息
        # 回退：显示基本信息
        basic = await api.get_match_result(league, stage, round_arg)
        if basic.ok and basic.value:
            yield event.plain_result(fmt.format_match_basic(basic.value))
            return
        async for message in self._render_query_result(
            event,
            Success(value=None),
            has_payload=lambda value: False,
            render_text=lambda value: "",
            render_image=lambda value: "",
            empty_text="⏳ 比赛详细信息暂未公布，请稍后再试。",
            error_prefix="/lol detail error",
        ):
            yield message

    @lol.command("standings")
    async def lol_standings(
        self,
        event: AstrMessageEvent,
        league: str = "lpl",
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

    # ═══════════════════════════════════════════════
    #  赛程扩展
    # ═══════════════════════════════════════════════

    @lol.command("today")
    async def lol_today(self, event: AstrMessageEvent, league: str = ""):
        """今日赛程。"""
        result = await api.get_today_schedule(league)
        match result:
            case Success(value=data) if data:
                text = fmt.format_schedule(data)
                yield event.plain_result(text)
            case Success():
                yield event.plain_result("📅 今天暂无比赛。")
            case Failure(error=err):
                yield event.plain_result(f"❌ {err}")

    @lol.command("week")
    async def lol_week(self, event: AstrMessageEvent, league: str = ""):
        """本周赛程。"""
        result = await api.get_week_schedule(league)
        match result:
            case Success(value=data) if data:
                text = fmt.format_schedule(data)
                yield event.plain_result(text)
            case Success():
                yield event.plain_result("📅 本周暂无比赛。")
            case Failure(error=err):
                yield event.plain_result(f"❌ {err}")

    # ═══════════════════════════════════════════════
    #  战队子命令组
    # ═══════════════════════════════════════════════

    @lol.group("team")
    def lol_team(self) -> None:
        """战队查询"""

    @lol_team.command("info")
    async def lol_team_info(self, event: AstrMessageEvent, team_id: str = ""):
        """战队列表。使用 /lol team info 查看所有战队，或 /lol team info <战队名> 筛选。"""
        result = await api.get_all_teams()
        match result:
            case Success(value=data):
                if isinstance(data, list):
                    if team_id.strip():
                        keyword = team_id.strip().lower()
                        filtered = [t for t in data if isinstance(t, dict) and keyword in str(t.get("name", t.get("slug", ""))).lower()]
                        if filtered:
                            yield event.plain_result(fmt.format_team_info({"teams": filtered}))
                        else:
                            yield event.plain_result(f"❌ 未找到匹配 '{team_id}' 的战队")
                    else:
                        yield event.plain_result(fmt.format_team_info({"teams": data}))
                else:
                    yield event.plain_result(fmt.format_team_info(data))
            case Failure(error=err):
                yield event.plain_result(f"❌ {err}")

    # ═══════════════════════════════════════════════
    #  选手子命令组
    # ═══════════════════════════════════════════════

    @lol.group("player")
    def lol_player(self) -> None:
        """选手查询"""

    @lol_player.command("stats")
    async def lol_player_stats(self, event: AstrMessageEvent, player_id: str = ""):
        """选手统计数据。"""
        if not player_id.strip():
            yield event.plain_result("请提供选手 ID。如: /lol player stats Faker")
            return
        result = await api.get_player_stats(player_id)
        match result:
            case Success(value=data):
                yield event.plain_result(fmt.format_player_stats(data))
            case Failure(error=err):
                yield event.plain_result(f"❌ {err}")

    @lol_player.command("earnings")
    async def lol_player_earnings(self, event: AstrMessageEvent, player_id: str = ""):
        """选手生涯奖金汇总。"""
        if not player_id.strip():
            yield event.plain_result("请提供选手 ID。如: /lol player earnings Faker")
            return
        result = await api.get_player_earnings_summary(player_id)
        match result:
            case Success(value=data):
                yield event.plain_result(fmt.format_player_earnings(data))
            case Failure(error=err):
                yield event.plain_result(f"❌ {err}")

    # ═══════════════════════════════════════════════
    #  转会
    # ═══════════════════════════════════════════════

    @lol.command("transfers")
    async def lol_transfers(self, event: AstrMessageEvent, league: str = ""):
        """转会信息。"""
        result = await api.get_transfers(league)
        match result:
            case Success(value=data):
                yield event.plain_result(fmt.format_transfers(data))
            case Failure(error=err):
                yield event.plain_result(f"❌ {err}")

    @lol.command("transfers-player")
    async def lol_transfers_player(self, event: AstrMessageEvent, player_id: str = ""):
        """选手转会历史。"""
        if not player_id.strip():
            yield event.plain_result("请提供选手 ID。如: /lol transfers-player Faker")
            return
        result = await api.get_transfers_player(player_id)
        match result:
            case Success(value=data):
                yield event.plain_result(fmt.format_transfers_player(data))
            case Failure(error=err):
                yield event.plain_result(f"❌ {err}")

    @lol.command("transfers-team")
    async def lol_transfers_team(self, event: AstrMessageEvent, team_slug: str = ""):
        """战队转会记录。"""
        if not team_slug.strip():
            yield event.plain_result("请提供战队名。如: /lol transfers-team T1")
            return
        result = await api.get_transfers_team(team_slug)
        match result:
            case Success(value=data):
                yield event.plain_result(fmt.format_transfers_team(data))
            case Failure(error=err):
                yield event.plain_result(f"❌ {err}")


    @lol.command("coverage")
    async def lol_coverage(self, event: AstrMessageEvent):
        """直播覆盖矩阵。"""
        result = await api.get_coverage()
        match result:
            case Success(value=data):
                yield event.plain_result(fmt.format_coverage(data))
            case Failure(error=err):
                yield event.plain_result(f"❌ {err}")

    # ──────────────── B站 官号视频查询 ────────────────

    @filter.command("lol bilibili")
    async def lol_bilibili(self, event: AstrMessageEvent):
        """查询 B 站 LOL 官号最新 5 条视频。"""
        items = await bili_fetcher.fetch_bilibili_updates()
        if not items:
            yield event.plain_result("📺 B站 LOL官号暂无可显示的视频。")
            return
        latest = items[:5]
        yield event.plain_result(fmt.format_bilibili_update(latest))

    # ──────────────── 微博赛前海报查询 ────────────────

    @filter.command("lol weibo")
    async def lol_weibo(self, event: AstrMessageEvent):
        """查询微博赛前海报最新 5 条。"""
        try:
            uid_list = get_weibo_uids(self._config)
            items = await weibo_fetcher.fetch_weibo_posters(uid_list)
        except Exception as e:
            yield event.plain_result(f"❌ 微博查询失败: {e}")
            return
        if not items:
            yield event.plain_result("📢 暂未发现相关赛前海报。")
            return
        latest = items[:5]
        yield event.plain_result(fmt.format_weibo_poster(latest))

    # ──────────────── 未知子指令兜底 ────────────────

    _KNOWN_SUB_COMMANDS: set[str] = {
        "help", "schedule", "next", "live", "result", "bp", "detail",
        "standings", "today", "week", "team", "player", "transfers",
        "transfers-player", "transfers-team", "coverage", "bilibili", "weibo",
        "subscribe", "unsubscribe", "apikey", "test",
    }

    @filter.regex(r"^/lol\s+\S")
    async def lol_fallback(self, event: AstrMessageEvent):
        """捕获 /lol 下未识别的子指令，提示并返回帮助。"""
        message = event.message_str.strip()
        sub_cmd = message.split(maxsplit=1)[1].split()[0]

        if sub_cmd not in self._KNOWN_SUB_COMMANDS:
            yield event.plain_result(f"❌ 该命令不存在：/lol {sub_cmd}\n\n{HELP_TEXT}")
