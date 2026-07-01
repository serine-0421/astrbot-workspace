"""AstrBot plugin: LoL Notifier

Provides LoL esports push notifications and on-demand query commands.
Data: PandaScore (primary) + citoapi (fallback).

Commands (prefix /lol):
    /lol help
    /lol schedule [league] [regular|playoff] [season]
    /lol next [league] [regular|playoff] [season]
    /lol live [league]
    /lol result [league] [regular|playoff] [round]
    /lol detail [league] [regular|playoff] [round]
    /lol standings [league] [regular|playoff] [season]
    /lol today [league]
    /lol game info|events|frames <game_id>
    /lol match games|stats <match_id>
    /lol team info [name] | team stats <team_id>
    /lol champions [version]   | champion <id>
    /lol items [version]        | item <id>
    /lol spells    | spell <id>
    /lol runes [paths|path <id>]  | rune <id>
    /lol masteries
    /lol series [league] [status] | series detail <id>
    /lol players [league]   | player <id> | player stats <id>
    /lol tournaments [league] [status] | tournament <id>
    /lol bilibili | weibo
    /lol subscribe | unsubscribe | apikey [key] | test [season]

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
from .src.astrbot_plugin_lol_notifier.config import get_weibo_uids, BILIBILI_ACCOUNTS
from .src.astrbot_plugin_lol_notifier import formatter as fmt
from .src.astrbot_plugin_lol_notifier import image_renderer as img
from .src.astrbot_plugin_lol_notifier.models import Failure, Success
from .src.astrbot_plugin_lol_notifier.scheduler import LoLScheduler

HELP_TEXT = """🎮 LoL Notifier 指令列表
📡 数据: PandaScore + citoapi

━━━ 比赛查询 ━━━
  /lol schedule [league] [regular|playoff] [season]
      近期赛程（默认 LPL，最近 5 场）
  /lol next [league] [regular|playoff] [season]
      下一场完整时间表
  /lol live [league]
      正在进行的实时比赛
  /lol result [league] [regular|playoff] [round]
      比赛结果（默认最近一场）
  /lol detail [league] [regular|playoff] [round]
      比赛详细信息（含对局数据）
  /lol standings [league] [regular|playoff] [season]
      排名 / 积分榜
  /lol today [league]
      今日赛程

━━━ 对局 & 比赛扩展 ━━━
  /lol game info <game_id>             单局详情
  /lol game events <game_id>           对局事伴
  /lol game frames <game_id>           对局帧数据
  /lol match games <match_id>          比赛所有对局
  /lol match stats <match_id>          比赛选手统计

━━━ 战队 & 选手 ━━━
  /lol team info [name]                战队信息
  /lol team stats <team_id>             战队统计
  /lol players [league]                选手列表
  /lol player <id>                     选手信息
  /lol player stats <id>                选手统计

━━━ 系列赛 & 锦标赛 ━━━
  /lol series [league] [status]        系列赛列表
  /lol series detail <id>              系列赛详情
  /lol tournaments [league] [status]   锦标赛列表
  /lol tournament <id>                 锦标赛详情

━━━ 参考数据 ━━━
  /lol champions [version]             英雄列表
  /lol champion <id_or_slug>           单个英雄
  /lol items [version]                 装备列表
  /lol item <id_or_slug>               单个装备
  /lol spells                          召唤师技能
  /lol spell <id>                      单个技能
  /lol runes                           符文列表 (reforged)
  /lol rune <id>                       单个符文详情
  /lol runes paths                     符文系列表
  /lol runes path <id>                 单个符文系详情
  /lol masteries                       天赋列表

━━━ B站 / 微博 ━━━
  /lol bilibili                        B站综合动态（视频·图文·直播）
  /lol weibo                           微博赛前海报

━━━ 赛区 ━━━
  lck lpl lec lcs lco lcl ljl pcs vcs cblol lla tcl msi worlds
  series status: past running upcoming

━━━ 管理 ━━━
  /lol subscribe / unsubscribe / apikey / test"""

_LEAGUE_SET = frozenset({
    "lck", "lpl", "lec", "lcs", "lco", "lcl", "ljl", "pcs", "vcs",
    "cblol", "lla", "tcl", "msi", "worlds",
})


def _parse_match_args(args: list[str]) -> tuple[str, str, str]:
    """智能解析 match 命令参数，识别 match ID / round 数字。

    /lol result LPL → ("lpl", "regular", "last")
    /lol result LPL 115616219464607521 → ("lpl", "regular", "115616219464607521")
    /lol result LPL regular 3 → ("lpl", "regular", "3")
    /lol result LPL playoff → ("lpl", "playoff", "last")
    """
    if not args:
        return ("lpl", "regular", "last")
    league = args[0]
    if len(args) == 1:
        return (league, "regular", "last")
    # 第二个参数可能是 stage 也可能是 round/match_id
    arg1 = args[1]
    if arg1.isdigit():
        # 纯数字 → match ID 或 round number
        return (league, "regular", arg1)
    if len(args) >= 3:
        return (league, arg1, args[2])
    # 非数字的单个第二参数 → stage，无 round
    return (league, arg1, "last")


@register(
    "astrbot_plugin_lol_notifier",
    "MareDevi",
    "LoL赛事推送与查询插件",
    "1.5.0",
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

    # ──────────── /lol 统一入口 — 正则分发（确保未知子命令也能被捕获）────────────
    @filter.regex(r"^/lol\b")
    @filter.event_message_type(filter.EventMessageType.ALL)
    async def _lol_dispatch(self, event: AstrMessageEvent):
        """解析 /lol 子命令并分发，未知命令返回帮助。"""
        msg = event.message_str.strip()
        parts = msg.split(maxsplit=1)
        if len(parts) == 1 or not parts[1].strip():
            yield event.plain_result(HELP_TEXT)
            return

        tail = parts[1].strip()
        sub_parts = tail.split()
        sub_cmd = sub_parts[0].lower()
        args = sub_parts[1:]  # remaining positional arguments

        async def _result(r):
            async for x in r:
                yield x

        try:
            if sub_cmd == "help":
                yield event.plain_result(HELP_TEXT)

            elif sub_cmd == "schedule":
                league = args[0] if len(args) > 0 else "lpl"
                stage = args[1] if len(args) > 1 else "regular"
                season = args[2] if len(args) > 2 else "current"
                async for m in _result(self._handle_schedule(event, league, stage, season)):
                    yield m

            elif sub_cmd == "next":
                league = args[0] if len(args) > 0 else "lpl"
                stage = args[1] if len(args) > 1 else "regular"
                season = args[2] if len(args) > 2 else "current"
                async for m in _result(self._handle_next(event, league, stage, season)):
                    yield m

            elif sub_cmd == "live":
                league = args[0] if len(args) > 0 else ""
                async for m in _result(self._handle_live(event, league)):
                    yield m

            elif sub_cmd == "result":
                league, stage, round_num = _parse_match_args(args)
                async for m in _result(self._handle_result(event, league, stage, round_num)):
                    yield m

            elif sub_cmd == "detail":
                league, stage, round_num = _parse_match_args(args)
                async for m in _result(self._handle_detail(event, league, stage, round_num)):
                    yield m

            elif sub_cmd == "standings":
                league = args[0] if len(args) > 0 else "lpl"
                stage = args[1] if len(args) > 1 else "regular"
                season = args[2] if len(args) > 2 else "current"
                async for m in _result(self._handle_standings(event, league, stage, season)):
                    yield m

            elif sub_cmd == "today":
                league = args[0] if len(args) > 0 else ""
                async for m in _result(self._handle_today(event, league)):
                    yield m

            elif sub_cmd == "subscribe":
                async for m in _result(self._handle_subscribe(event)):
                    yield m

            elif sub_cmd == "unsubscribe":
                async for m in _result(self._handle_unsubscribe(event)):
                    yield m

            elif sub_cmd == "apikey":
                key_arg = args[0] if len(args) > 0 else ""
                async for m in _result(self._handle_apikey(event, key_arg)):
                    yield m

            elif sub_cmd == "test":
                season = args[0] if len(args) > 0 else "current"
                async for m in _result(self._handle_test(event, season)):
                    yield m

            elif sub_cmd == "bilibili":
                async for m in _result(self._handle_bilibili(event)):
                    yield m

            elif sub_cmd == "weibo":
                async for m in _result(self._handle_weibo(event)):
                    yield m

            elif sub_cmd == "game":
                sub2 = args[0].lower() if len(args) > 0 else "info"
                game_id = args[1] if len(args) > 1 else ""
                if sub2 == "info" and game_id:
                    async for m in _result(self._handle_game_info(event, game_id)):
                        yield m
                elif sub2 == "events" and game_id:
                    async for m in _result(self._handle_game_events(event, game_id)):
                        yield m
                elif sub2 == "frames" and game_id:
                    async for m in _result(self._handle_game_frames(event, game_id)):
                        yield m
                else:
                    yield event.plain_result(f"❌ 用法: /lol game <info|events|frames> <game_id>")

            elif sub_cmd == "champions":
                version = args[0] if len(args) > 0 else ""
                async for m in _result(self._handle_champions(event, version)):
                    yield m

            elif sub_cmd == "champion":
                cid = args[0] if len(args) > 0 else ""
                if cid:
                    async for m in _result(self._handle_champion(event, cid)):
                        yield m
                else:
                    yield event.plain_result("❌ 用法: /lol champion <id_or_slug>")

            elif sub_cmd == "items":
                version = args[0] if len(args) > 0 else ""
                async for m in _result(self._handle_items(event, version)):
                    yield m

            elif sub_cmd == "item":
                iid = args[0] if len(args) > 0 else ""
                if iid:
                    async for m in _result(self._handle_item(event, iid)):
                        yield m
                else:
                    yield event.plain_result("❌ 用法: /lol item <id_or_slug>")

            elif sub_cmd == "spells":
                async for m in _result(self._handle_spells(event)):
                    yield m

            elif sub_cmd == "spell":
                sid = args[0] if len(args) > 0 else ""
                if sid:
                    async for m in _result(self._handle_spell(event, sid)):
                        yield m
                else:
                    yield event.plain_result("❌ 用法: /lol spell <id>")

            elif sub_cmd == "runes":
                sub2 = args[0].lower() if len(args) > 0 else "list"
                if sub2 == "paths":
                    async for m in _result(self._handle_rune_paths(event)):
                        yield m
                elif sub2 == "path":
                    pid = args[1] if len(args) > 1 else ""
                    if pid:
                        async for m in _result(self._handle_rune_path(event, pid)):
                            yield m
                    else:
                        yield event.plain_result("❌ 用法: /lol runes path <id>")
                else:
                    async for m in _result(self._handle_runes(event)):
                        yield m

            elif sub_cmd == "rune":
                rid = args[0] if len(args) > 0 else ""
                if rid:
                    async for m in _result(self._handle_rune(event, rid)):
                        yield m
                else:
                    yield event.plain_result("❌ 用法: /lol rune <id>")

            elif sub_cmd == "masteries":
                async for m in _result(self._handle_masteries(event)):
                    yield m

            elif sub_cmd == "series":
                sub2 = args[0].lower() if len(args) > 0 else ""
                if sub2 == "detail":
                    sid = args[1] if len(args) > 1 else ""
                    if sid:
                        async for m in _result(self._handle_series_detail(event, sid)):
                            yield m
                    else:
                        yield event.plain_result("❌ 用法: /lol series detail <id>")
                elif sub2 in _LEAGUE_SET:
                    league = sub2
                    status = args[1].lower() if len(args) > 1 else ""
                    async for m in _result(self._handle_series(event, league, status)):
                        yield m
                elif sub2 in ("past", "running", "upcoming"):
                    status = sub2
                    league = args[1].lower() if len(args) > 1 else ""
                    async for m in _result(self._handle_series(event, league, status)):
                        yield m
                else:
                    async for m in _result(self._handle_series(event, "", "")):
                        yield m

            elif sub_cmd == "players":
                league = args[0] if len(args) > 0 else ""
                async for m in _result(self._handle_players(event, league)):
                    yield m

            elif sub_cmd == "player":
                sub2 = args[0].lower() if len(args) > 0 else ""
                pid = args[1] if len(args) > 1 else ""
                if sub2 == "stats" and pid:
                    async for m in _result(self._handle_player_stats(event, pid)):
                        yield m
                elif sub2:
                    async for m in _result(self._handle_player(event, sub2)):
                        yield m
                else:
                    yield event.plain_result("❌ 用法: /lol player <id> | /lol player stats <id>")

            elif sub_cmd == "tournaments":
                league = args[0] if len(args) > 0 else ""
                status = args[1].lower() if len(args) > 1 else ""
                async for m in _result(self._handle_tournaments(event, league, status)):
                    yield m

            elif sub_cmd == "tournament":
                tid = args[0] if len(args) > 0 else ""
                if tid:
                    async for m in _result(self._handle_tournament(event, tid)):
                        yield m
                else:
                    yield event.plain_result("❌ 用法: /lol tournament <id>")

            elif sub_cmd == "match":
                sub2 = args[0].lower() if len(args) > 0 else ""
                mid = args[1] if len(args) > 1 else ""
                if sub2 == "games" and mid:
                    async for m in _result(self._handle_match_games(event, mid)):
                        yield m
                elif sub2 == "stats" and mid:
                    async for m in _result(self._handle_match_players_stats(event, mid)):
                        yield m
                else:
                    yield event.plain_result("❌ 用法: /lol match games <id> | /lol match stats <id>")

            elif sub_cmd == "team":
                sub2 = args[0].lower() if len(args) > 0 else "info"
                if sub2 == "stats":
                    tid = args[1] if len(args) > 1 else ""
                    if tid:
                        async for m in _result(self._handle_team_stats(event, tid)):
                            yield m
                    else:
                        yield event.plain_result("❌ 用法: /lol team stats <team_id>")
                elif sub2 == "info":
                    name = args[1] if len(args) > 1 else ""
                    async for m in _result(self._handle_team_info(event, name)):
                        yield m
                else:
                    # 回退兼容: /lol team <name>
                    async for m in _result(self._handle_team_info(event, args[0])):
                        yield m

            else:
                yield event.plain_result(f"❌ 该命令不存在：/lol {sub_cmd}\n\n{HELP_TEXT}")

        except Exception as exc:
            logger.error(f"[LoLNotifier] Dispatch error for /lol {sub_cmd}: {exc}")
            yield event.plain_result(f"❌ 命令执行出错：{exc}\n\n{HELP_TEXT}")

    # ═══════════════════════════════════════════════
    #  命令处理方法（无装饰器，由 _lol_dispatch 调用）
    # ═══════════════════════════════════════════════

    async def _handle_schedule(self, event, league, stage, season):
        result = await api.get_schedule(league, stage, season)
        async for msg in self._render_query_result(
            event, result,
            has_payload=lambda v: bool(v),
            render_text=lambda v: fmt.format_schedule(v),
            render_image=lambda v: img.render_schedule(v),
            empty_text="⏳ 暂未找到可显示的赛程信息，请稍后再试。",
            error_prefix="/lol schedule error",
        ):
            yield msg

    async def _handle_next(self, event, league, stage, season):
        result = await api.get_schedule(league, stage, season)
        match result:
            case Success(value=schedule) if schedule:
                unstarted = [m for m in schedule if m.status in ("unstarted", "")]
                in_progress = [m for m in schedule if m.status in ("in_progress", "live")]
                if unstarted:
                    unstarted.sort(key=lambda m: (m.start_date, m.start_time))
                    next_match = unstarted[0]
                    is_past = False
                elif in_progress:
                    next_match = in_progress[0]
                    is_past = False
                else:
                    fallback = await self._find_next_in_other_leagues(league, stage, season)
                    if fallback is not None:
                        fm, fl = fallback
                        text = fmt.format_schedule([fm], limit=1)
                        text = text.replace("📅 LoL 近期赛程", f"⏭️ 下一场比赛（{league.upper()}暂无未来赛程，最近是 {fl.upper()}）")
                        image_path = await img.render_schedule([fm], limit=1)
                        yield await self._render_or_text(event, text, image_path)
                        return
                    completed = [m for m in schedule if m.status in ("completed", "finished")]
                    if completed:
                        completed.sort(key=lambda m: (m.start_date, m.start_time), reverse=True)
                        next_match = completed[0]
                    else:
                        sorted_matches = sorted(schedule, key=lambda m: (m.start_date, m.start_time), reverse=True)
                        next_match = sorted_matches[0]
                    is_past = True
                if is_past:
                    text = fmt.format_schedule([next_match], limit=1)
                    text = text.replace("📅 LoL 近期赛程", "📅 最近一场比赛（暂无未来赛程）")
                else:
                    text = fmt.format_schedule([next_match], limit=1)
                    text = text.replace("📅 LoL 近期赛程", "⏭️ 下一场比赛")
                image_path = await img.render_schedule([next_match], limit=1)
                yield await self._render_or_text(event, text, image_path)
            case Success():
                fallback = await self._find_next_in_other_leagues(league, stage, season)
                if fallback is not None:
                    fm, fl = fallback
                    text = fmt.format_schedule([fm], limit=1)
                    text = text.replace("📅 LoL 近期赛程", f"⏭️ 下一场比赛（{league.upper()}暂无赛程，最近是 {fl.upper()}）")
                    image_path = await img.render_schedule([fm], limit=1)
                    yield await self._render_or_text(event, text, image_path)
                    return
                yield event.plain_result("📅 当前没有可显示的赛程信息。")
            case Failure(error=err):
                logger.error(f"[LoLNotifier] /lol next error: {err}")
                yield event.plain_result(f"❌ 获取下一场赛程失败：{err}")

    async def _find_next_in_other_leagues(self, original_league: str, stage: str, season: str):
        _FALLBACK_ORDER = [
            "msi", "worlds", "lck", "lpl", "lec", "lcs",
            "pcs", "vcs", "lco", "ljl", "cblol", "lla", "lcl", "tcl",
        ]
        original_lower = original_league.strip().lower()
        for fl in _FALLBACK_ORDER:
            if fl == original_lower:
                continue
            result = await api.get_schedule(fl, stage, season)
            if result.ok and result.value:
                unstarted = [m for m in result.value if m.status in ("unstarted", "")]
                in_progress = [m for m in result.value if m.status in ("in_progress", "live")]
                if unstarted:
                    unstarted.sort(key=lambda m: (m.start_date, m.start_time))
                    return (unstarted[0], fl)
                if in_progress:
                    return (in_progress[0], fl)
        return None

    async def _handle_live(self, event, league):
        from .src.astrbot_plugin_lol_notifier.formatter.message import format_live_match
        result = await api.get_live_matches(league)
        match result:
            case Success(value=detailed) if detailed:
                lines_parts = [format_live_match(lm) for lm in detailed]
                yield event.plain_result("\n\n".join(lines_parts))
            case Success():
                yield event.plain_result("📡 当前没有正在进行的比赛。")
            case Failure(error=err):
                logger.error(f"[LoLNotifier] /lol live error: {err}")
                yield event.plain_result(f"❌ 获取实时比赛数据失败：{err}")

    async def _handle_result(self, event, league, stage, round_num):
        round_arg: int | str = int(round_num) if round_num.isdigit() else "last"
        detail_result = await api.get_match_detail(league, stage, round_arg)
        if detail_result.ok and detail_result.value and detail_result.value.games:
            async for msg in self._render_query_result(
                event, detail_result,
                has_payload=lambda v: bool(v.games),
                render_text=lambda v: fmt.format_match_detail(v),
                render_image=lambda v: img.render_match_detail(v),
                empty_text="⏳ 比赛结果暂未公布，请比赛结束后再试。",
                error_prefix="/lol result error",
            ):
                yield msg
            return
        result = await api.get_match_result(league, stage, round_arg)
        async for msg in self._render_query_result(
            event, result,
            has_payload=lambda v: v is not None,
            render_text=lambda v: fmt.format_match_basic(v),
            render_image=lambda v: img.render_match_result(v),
            empty_text="⏳ 比赛结果暂未公布，请比赛结束后再试。",
            error_prefix="/lol result error",
        ):
            yield msg

    async def _handle_detail(self, event, league, stage, round_num):
        round_arg: int | str = int(round_num) if round_num.isdigit() else "last"
        result = await api.get_match_detail(league, stage, round_arg)
        if result.ok and result.value and result.value.games:
            async for msg in self._render_query_result(
                event, result,
                has_payload=lambda v: bool(v.games),
                render_text=lambda v: fmt.format_match_detail(v),
                render_image=lambda v: img.render_match_detail(v),
                empty_text="⏳ 比赛详细信息暂未公布，请稍后再试。",
                error_prefix="/lol detail error",
            ):
                yield msg
            return
        basic = await api.get_match_result(league, stage, round_arg)
        if basic.ok and basic.value:
            yield event.plain_result(fmt.format_match_basic(basic.value))
            return
        async for msg in self._render_query_result(
            event, Success(value=None),
            has_payload=lambda v: False, render_text=lambda v: "", render_image=lambda v: "",
            empty_text="⏳ 比赛详细信息暂未公布，请稍后再试。",
            error_prefix="/lol detail error",
        ):
            yield msg

    async def _handle_standings(self, event, league, stage, season):
        result = await api.get_standings(league, stage, season)
        async for msg in self._render_query_result(
            event, result,
            has_payload=lambda v: bool(v),
            render_text=lambda v: fmt.format_standings(v),
            render_image=lambda v: img.render_standings(v),
            empty_text="⏳ 暂未找到可显示的排名/积分榜，请稍后再试。",
            error_prefix="/lol standings error",
        ):
            yield msg

    async def _handle_today(self, event, league):
        result = await api.get_today_schedule(league)
        match result:
            case Success(value=data) if data:
                yield event.plain_result(fmt.format_schedule(data))
            case Success():
                yield event.plain_result("📅 今天暂无比赛。")
            case Failure(error=err):
                yield event.plain_result(f"❌ {err}")

    async def _handle_team_info(self, event, team_id):
        result = await api.get_all_teams()
        match result:
            case Success(value=data):
                if isinstance(data, list):
                    if team_id.strip():
                        keyword = team_id.strip().lower()
                        filtered = [
                            t for t in data
                            if isinstance(t, dict) and (
                                keyword in str(t.get("name", "")).lower()
                                or keyword in str(t.get("acronym", "")).lower()
                                or keyword in str(t.get("slug", "")).lower()
                            )
                        ]
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

    async def _handle_game_info(self, event, game_id):
        result = await api.get_game_detail(game_id)
        match result:
            case Success(value=data) if isinstance(data, dict):
                yield event.plain_result(fmt.format_game_info(data))
            case Success():
                yield event.plain_result(f"❌ 未找到对局 {game_id} 的信息。")
            case Failure(error=err):
                yield event.plain_result(f"❌ {err}")

    async def _handle_subscribe(self, event):
        session = event.unified_msg_origin
        added = await self.scheduler.add_subscriber(session)
        if added:
            yield event.plain_result(f"✅ 已订阅 LoL 自动推送！\n当前共 {self.scheduler.subscriber_count()} 个会话已订阅。")
        else:
            yield event.plain_result("ℹ️ 当前会话已经订阅过了。发送 /lol unsubscribe 可以取消。")

    async def _handle_unsubscribe(self, event):
        session = event.unified_msg_origin
        removed = await self.scheduler.remove_subscriber(session)
        if removed:
            yield event.plain_result("✅ 已取消订阅 LoL 自动推送。")
        else:
            yield event.plain_result("ℹ️ 当前会话尚未订阅。发送 /lol subscribe 可以订阅。")

    async def _handle_apikey(self, event, key):
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
            f"🔑 citoapi Key 状态\n\n  Key: {masked}\n  来源: {source}\n  citoapi Key 长期有效，无需刷新\n\n"
            f"💡 设置新 Key: /lol apikey <你的key>\n💡 环境变量: CITO_API_KEY"
        )

    async def _handle_test(self, event, season):
        year = season if season else "current"
        yield event.plain_result(f"🔧 正在测试 {year} 赛季数据，请稍候...")

        async def run(name, coro):
            r = await coro
            match r:
                case Success(value=val):
                    if isinstance(val, list):
                        return (name, True, f"✅ {len(val)} 条记录")
                    label = getattr(val, "match_name", None) or getattr(val, "league", None) or getattr(val, "stage", None)
                    return (name, True, f"✅ {label or ''}")
                case Failure(error=err):
                    return (name, False, f"❌ {err}")
            return (name, False, "❌ unknown")

        results = list(await asyncio.gather(
            run("赛程(LCK)", api.get_schedule("lck", "regular", year)),
            run("赛程(LPL)", api.get_schedule("lpl", "regular", year)),
            run("赛程(LEC)", api.get_schedule("lec", "regular", year)),
            run("比赛结果", api.get_match_result("lck", "regular", "last")),
            run("详细信息", api.get_match_detail("lpl", "regular", "last")),
            run("积分/排名", api.get_standings("lck", "regular", year)),
        ))
        lines = [f"📋 LoL 插件测试报告 ({year})\n"]
        passed = sum(1 for _, ok, _ in results if ok)
        for name, ok, detail in results:
            lines.append(f"  {'✅' if ok else '❌'} {name}: {detail}")
        lines.append(f"\n共 {passed}/{len(results)} 项通过")
        yield event.plain_result("\n".join(lines))

    async def _handle_bilibili(self, event):
        """产出 B站 三账号综合动态摘要。"""
        parts: list[str] = []

        for account in BILIBILI_ACCOUNTS:
            uid = account["uid"]
            name = account["name"]

            # ── 视频 ──
            videos = await bili_fetcher.fetch_bilibili_updates(uid)
            if videos:
                lines = [f"📺 **{name}**  · 视频"]
                for v in videos[:3]:
                    lines.append(f"  ▸ {v.get('title','')}  {v.get('url','')}")
                parts.append("\n".join(lines))

            # ── 图文动态 ──
            dynamics = await bili_fetcher.fetch_bilibili_dynamics(uid)
            if dynamics:
                lines = [f"📰 **{name}**  · 图文动态"]
                for d in dynamics[:3]:
                    text = d.get("text", "")[:60]
                    lines.append(f"  ▸ {text}... {d.get('url','')}")
                parts.append("\n".join(lines))

            # ── 直播 ──
            lives = await bili_fetcher.fetch_bilibili_live_status(uid)
            for live in lives:
                if live.get("live_status") == 1:
                    parts.append(
                        f"🔴 **{name}**  · 正在直播\n"
                        f"  ▸ {live.get('title','')}\n"
                        f"  ▸ 人气 {live.get('online',0):,}  {live.get('url','')}"
                    )
                else:
                    parts.append(f"⏸️ **{name}**  · 直播未开播")

        if not parts:
            yield event.plain_result("📺 所有 B站 账号暂无可显示的内容。")
            return

        yield event.plain_result("\n\n".join(parts))

    async def _handle_weibo(self, event):
        try:
            uid_list = get_weibo_uids(self._config)
            items = await weibo_fetcher.fetch_weibo_posters(uid_list)
        except Exception as e:
            yield event.plain_result(f"❌ 微博查询失败: {e}")
            return
        if not items:
            yield event.plain_result("📢 暂未发现相关赛前海报。")
            return
        yield event.plain_result(fmt.format_weibo_poster(items[:5]))

    # ═══════════════════════════════════════════════
    #  参考数据 — Champions / Items / Spells / Runes / Masteries
    # ═══════════════════════════════════════════════

    async def _handle_champions(self, event, version: str):
        result = await api.get_champions(version or "")
        match result:
            case Success(value=data):
                yield event.plain_result(fmt.format_champions(data, limit=15))
            case Failure(error=err):
                yield event.plain_result(f"❌ {err}")

    async def _handle_champion(self, event, cid: str):
        result = await api.get_champion(cid)
        match result:
            case Success(value=data):
                yield event.plain_result(fmt.format_champions([data], limit=1))
            case Failure(error=err):
                yield event.plain_result(f"❌ {err}")

    async def _handle_items(self, event, version: str):
        result = await api.get_items(version or "")
        match result:
            case Success(value=data):
                yield event.plain_result(fmt.format_items(data, limit=15))
            case Failure(error=err):
                yield event.plain_result(f"❌ {err}")

    async def _handle_item(self, event, iid: str):
        result = await api.get_item(iid)
        match result:
            case Success(value=data):
                yield event.plain_result(fmt.format_items([data], limit=1))
            case Failure(error=err):
                yield event.plain_result(f"❌ {err}")

    async def _handle_spells(self, event):
        result = await api.get_spells()
        match result:
            case Success(value=data):
                yield event.plain_result(fmt.format_spells(data))
            case Failure(error=err):
                yield event.plain_result(f"❌ {err}")

    async def _handle_spell(self, event, sid: str):
        result = await api.get_spell(sid)
        match result:
            case Success(value=data):
                yield event.plain_result(fmt.format_spells([data]))
            case Failure(error=err):
                yield event.plain_result(f"❌ {err}")

    async def _handle_runes(self, event):
        result = await api.get_runes()
        match result:
            case Success(value=data):
                yield event.plain_result(fmt.format_runes(data, limit=25))
            case Failure(error=err):
                yield event.plain_result(f"❌ {err}")

    async def _handle_rune_paths(self, event):
        result = await api.get_rune_paths()
        match result:
            case Success(value=data):
                yield event.plain_result(fmt.format_rune_paths(data))
            case Failure(error=err):
                yield event.plain_result(f"❌ {err}")

    async def _handle_rune(self, event, rune_id: str):
        result = await api.get_rune(rune_id)
        match result:
            case Success(value=data):
                yield event.plain_result(fmt.format_runes(data, limit=1))
            case Failure(error=err):
                yield event.plain_result(f"❌ {err}")

    async def _handle_rune_path(self, event, path_id: str):
        result = await api.get_rune_path(path_id)
        match result:
            case Success(value=data):
                yield event.plain_result(fmt.format_rune_paths(data))
            case Failure(error=err):
                yield event.plain_result(f"❌ {err}")

    async def _handle_masteries(self, event):
        result = await api.get_masteries()
        match result:
            case Success(value=data):
                yield event.plain_result(fmt.format_masteries(data))
            case Failure(error=err):
                yield event.plain_result(f"❌ {err}")

    # ═══════════════════════════════════════════════
    #  对局扩展 — Events / Frames / Match Games / Stats
    # ═══════════════════════════════════════════════

    async def _handle_game_events(self, event, game_id: str):
        result = await api.get_game_events(game_id)
        match result:
            case Success(value=data):
                yield event.plain_result(fmt.format_game_events(data, limit=50))
            case Failure(error=err):
                yield event.plain_result(f"❌ {err}")

    async def _handle_game_frames(self, event, game_id: str):
        result = await api.get_game_frames(game_id)
        match result:
            case Success(value=data):
                yield event.plain_result(fmt.format_game_frames(data, limit=20))
            case Failure(error=err):
                yield event.plain_result(f"❌ {err}")

    async def _handle_match_games(self, event, match_id: str):
        result = await api.get_match_games(match_id)
        match result:
            case Success(value=data):
                yield event.plain_result(fmt.format_match_games(data))
            case Failure(error=err):
                yield event.plain_result(f"❌ {err}")

    async def _handle_match_players_stats(self, event, match_id: str):
        result = await api.get_match_players_stats(match_id)
        match result:
            case Success(value=data):
                yield event.plain_result(fmt.format_match_players_stats(data, limit=15))
            case Failure(error=err):
                yield event.plain_result(f"❌ {err}")

    # ═══════════════════════════════════════════════
    #  选手 & 战队统计
    # ═══════════════════════════════════════════════

    async def _handle_players(self, event, league: str):
        result = await api.get_players(league or "")
        match result:
            case Success(value=data):
                yield event.plain_result(fmt.format_players(data, limit=20))
            case Failure(error=err):
                yield event.plain_result(f"❌ {err}")

    async def _handle_player(self, event, pid: str):
        result = await api.get_player(pid)
        match result:
            case Success(value=data):
                yield event.plain_result(fmt.format_player(data))
            case Failure(error=err):
                yield event.plain_result(f"❌ {err}")

    async def _handle_player_stats(self, event, pid: str):
        result = await api.get_player_stats(pid)
        match result:
            case Success(value=data):
                yield event.plain_result(fmt.format_player_stats(data))
            case Failure(error=err):
                yield event.plain_result(f"❌ {err}")

    async def _handle_team_stats(self, event, tid: str):
        result = await api.get_team_stats(tid)
        match result:
            case Success(value=data):
                yield event.plain_result(fmt.format_team_stats(data))
            case Failure(error=err):
                yield event.plain_result(f"❌ {err}")

    # ═══════════════════════════════════════════════
    #  系列赛 & 锦标赛
    # ═══════════════════════════════════════════════

    async def _handle_series(self, event, league: str, status: str):
        result = await api.get_series(league or "", status or "")
        match result:
            case Success(value=data):
                yield event.plain_result(fmt.format_series(data, limit=10))
            case Failure(error=err):
                yield event.plain_result(f"❌ {err}")

    async def _handle_series_detail(self, event, sid: str):
        result = await api.get_series_detail(sid)
        match result:
            case Success(value=data):
                yield event.plain_result(fmt.format_series_detail(data))
            case Failure(error=err):
                yield event.plain_result(f"❌ {err}")

    async def _handle_tournaments(self, event, league: str, status: str):
        result = await api.get_tournaments(league or "", status or "")
        match result:
            case Success(value=data):
                yield event.plain_result(fmt.format_tournaments(data, limit=10))
            case Failure(error=err):
                yield event.plain_result(f"❌ {err}")

    async def _handle_tournament(self, event, tid: str):
        result = await api.get_tournament(tid)
        match result:
            case Success(value=data):
                yield event.plain_result(fmt.format_tournament(data))
            case Failure(error=err):
                yield event.plain_result(f"❌ {err}")
