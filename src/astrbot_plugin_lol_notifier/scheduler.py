"""Background scheduler for LoL notifications.

推送场景：
  1. B站 哔哩哔哩英雄联盟赛事 (UID 50329118) → 视频更新
  2. 微博 英雄联盟赛事 (UID 6537214902) → 赛前海报 (LPL+预告关键词)
  3. B站 BLG电子竞技俱乐部 (UID 268999208) → BP图文动态
  4. 距比赛日 ≤ 24h → 赛程 + 对阵表 + 海报
  5. 赛前 30min → 首发名单 + 交手记录 + 预测
  6. 每小局 BP 结束 → 阵容名单
  7. 每小局结束 → 胜负 + 战报
  8. 比赛结束 → 最终比分 + MVP + 回放
  9. 淘汰赛关键节点 → 晋级/淘汰
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from astrbot.api import logger
from astrbot.api.event import MessageChain
from astrbot.api.message_components import Image, Plain

from . import image_renderer as img
from .config import (
    BILIBILI_ACCOUNTS,
    get_weibo_uids,
    is_bilibili_push_enabled,
    is_any_bilibili_push_enabled,
    is_weibo_poster_push_enabled,
    is_daily_schedule_enabled,
    is_pre_match_reminder_enabled,
    get_schedule_push_time,
    get_schedule_leagues,
)
from .fetcher import api as fetcher_api
from .fetcher import bilibili, weibo
from .formatter import message as formatter
from .models import Failure, LeagueMatch, LiveMatch, Success
from .state import NotificationState, default_state

if TYPE_CHECKING:
    from astrbot.api import AstrBotConfig
    from astrbot.api.star import Star
    from astrbot.core.star.context import Context


# 主轮询间隔: 5 分钟（用于 B站/微博等第三方平台检查）
POLL_INTERVAL = 300
# 并行广播并发数
BROADCAST_CONCURRENCY = 5


class LoLScheduler:
    """Manages automated LoL push notifications."""

    def __init__(
        self, star: Star, context: Context, config: AstrBotConfig | None = None
    ) -> None:
        self.ctx = context
        self._star = star
        self._config = config
        self._subscribers: list[str] = []
        self._state: NotificationState = default_state()
        self._task: asyncio.Task | None = None
        self._loaded = False
        # 用于分离不同数据的轮询频率
        self._last_schedule_poll: float = 0.0
        self._last_live_poll: float = 0.0
        img.configure(config)

    # ── 属性 ──

    @property
    def _image_mode(self) -> bool:
        return bool(self._config.get("enable_image_render", False)) if self._config else False

    # ── 生命周期 ──

    def start(self) -> None:
        if self._task is None or self._task.done():
            # B站 Cookie 已在 bilibili.py 模块初始化时自动加载
            # （来源：_DEFAULT_COOKIE 常量 或 环境变量 BILIBILI_COOKIE）
            self._task = asyncio.create_task(self._run())
            logger.info("[LoLNotifier] Scheduler started.")

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            logger.info("[LoLNotifier] Scheduler stopped.")

    # ── 订阅管理 ──

    async def add_subscriber(self, session: str) -> bool:
        if session not in self._subscribers:
            self._subscribers.append(session)
            await self._persist_subscribers()
            return True
        return False

    async def remove_subscriber(self, session: str) -> bool:
        if session in self._subscribers:
            self._subscribers.remove(session)
            await self._persist_subscribers()
            return True
        return False

    def has_subscriber(self, session: str) -> bool:
        return session in self._subscribers

    def subscriber_count(self) -> int:
        return len(self._subscribers)

    # ── 持久化 ──

    async def _load(self) -> None:
        self._subscribers = await self._star.get_kv_data("lol_subscribers", []) or []
        state_dict = await self._star.get_kv_data("lol_state", None)
        if state_dict:
            try:
                self._state = NotificationState(**state_dict)
            except Exception as e:
                logger.warning(f"[LoLNotifier] Failed to load state, using default: {e}")
                self._state = default_state()
        else:
            self._state = default_state()
        self._loaded = True
        logger.info(f"[LoLNotifier] Loaded {len(self._subscribers)} subscriber(s) from KV store.")

    async def _persist_subscribers(self) -> None:
        await self._star.put_kv_data("lol_subscribers", self._subscribers)

    async def _persist_state(self) -> None:
        state_dict = {
            "first_match_reminded": self._state.first_match_reminded,
            "pre_match_notice": self._state.pre_match_notice,
            "bp_round_notice": self._state.bp_round_notice,
            "post_round_notice": self._state.post_round_notice,
            "elimination_updates": self._state.elimination_updates,
            "daily_schedule_sent_date": self._state.daily_schedule_sent_date,
            "pre_match_10min_notified": list(self._state.pre_match_10min_notified),
            "bilibili_video_seen": {k: list(v) for k, v in self._state.bilibili_video_seen.items()},
            "bilibili_dynamic_seen": {k: list(v) for k, v in self._state.bilibili_dynamic_seen.items()},
            "bilibili_live_state": self._state.bilibili_live_state,
            "weibo_updates": list(self._state.weibo_updates),
        }
        await self._star.put_kv_data("lol_state", state_dict)

    async def _run(self) -> None:
        await self._load()
        while True:
            try:
                if self._subscribers:
                    await self._check_and_notify()
                await asyncio.sleep(POLL_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[LoLNotifier] Scheduler error: {e}", exc_info=True)
                await asyncio.sleep(POLL_INTERVAL)

    async def _check_and_notify(self) -> None:
        """主推送检查逻辑：按时机触发各类通知。"""
        now = datetime.now(timezone.utc)

        # ═══ 每日赛程推送（北京时间 8:00） ═══
        if is_daily_schedule_enabled(self._config):
            await self._check_daily_schedule(now)

        # ═══ 赛前 10 分钟预告 ═══
        if is_pre_match_reminder_enabled(self._config):
            await self._check_pre_match_10min(now)

        # ═══ 第三方平台推送 ═══

        # 1. B站多账号 → 视频+图文动态 (per-account per-type toggle)
        await self._check_bilibili_feeds()

        # 2. 微博 英雄联盟赛事 (UID 6537214902) → 赛前海报 (LPL+预告)
        await self._check_weibo_posters()

    async def _broadcast(self, text: str, image_path: str | None = None) -> None:
        """广播消息到所有订阅者"""
        if not self._subscribers:
            return
        
        chain = None
        if self._image_mode and image_path:
            try:
                chain = MessageChain([Image.fromFileSystem(image_path)])
            except Exception as e:
                logger.warning(f"[LoLNotifier] Image broadcast failed, fallback to text: {e}")
        
        if chain is None:
            chain = MessageChain([Plain(text)])
        
        sem = asyncio.Semaphore(BROADCAST_CONCURRENCY)
        
        async def _send(session_str: str) -> None:
            async with sem:
                try:
                    ok = await self.ctx.send_message(session_str, chain)
                    if not ok:
                        logger.warning(f"[LoLNotifier] Failed to send to {session_str}")
                except Exception as e:
                    logger.error(f"[LoLNotifier] Broadcast error to {session_str}: {e}")
        
        await asyncio.gather(*[_send(s) for s in self._subscribers.copy()])

    # ──────────────── 推送时机检查 ────────────────────

    async def _check_24h_before_match(self, match: LeagueMatch, now: datetime) -> None:
        """距第一个比赛日 ≤ 24小时：推送当日赛程 + 对阵表 + 双方战队海报"""
        if self._state.first_match_reminded:
            return
        
        try:
            match_time = datetime.fromisoformat(f"{match.start_date}T{match.start_time}")
            if match_time.tzinfo is None:
                match_time = match_time.replace(tzinfo=timezone.utc)
            
            time_until = (match_time - now).total_seconds()
            if 0 < time_until <= 86400:  # 24小时内
                # 获取海报
                uids = get_weibo_uids(self._config)
                posters = await weibo.fetch_weibo_posters(uids) if uids else []
                poster_text = "\n".join([p.get("url", "") for p in posters[:2]]) if posters else ""
                
                text = formatter.format_pre_match_preview(
                    match,
                    history=None,
                    prediction=None,
                    posters=poster_text
                )
                text = f"⏰ 距离比赛开始不到 24 小时！\n\n{text}"
                
                image_path = await img.render_schedule([match], limit=1)
                await self._broadcast(text, image_path)
                
                self._state.first_match_reminded = True
                await self._persist_state()
                logger.info(f"[LoLNotifier] Sent 24h reminder for {match.match_name}")
        except Exception as e:
            logger.error(f"[LoLNotifier] Error in 24h check: {e}")

    async def _check_30min_before_match(self, match: LeagueMatch, now: datetime) -> None:
        """比赛开始前 30 分钟：首发名单 + 历史交手记录 + 赛前预测 + 双方海报"""
        match_key = f"{match.league}_{match.stage}_{match.round}"
        if self._state.pre_match_notice.get(match_key):
            return
        
        try:
            match_time = datetime.fromisoformat(f"{match.start_date}T{match.start_time}")
            if match_time.tzinfo is None:
                match_time = match_time.replace(tzinfo=timezone.utc)
            
            time_until = (match_time - now).total_seconds()
            if 0 < time_until <= 1800:  # 30分钟内
                # 获取海报
                uids = get_weibo_uids(self._config)
                posters = await weibo.fetch_weibo_posters(uids) if uids else []
                poster_text = "\n".join([p.get("url", "") for p in posters[:2]]) if posters else ""
                
                text = formatter.format_pre_match_preview(
                    match,
                    history="历史交手数据尚未接入",
                    prediction="赛前预测数据尚未接入",
                    posters=poster_text
                )
                
                await self._broadcast(text, None)
                
                self._state.pre_match_notice[match_key] = True
                await self._persist_state()
                logger.info(f"[LoLNotifier] Sent 30min preview for {match_key}")
        except Exception as e:
            logger.error(f"[LoLNotifier] Error in 30min check: {e}")

    async def _check_bp_finished(self, match: LeagueMatch, now: datetime) -> None:
        """每小局 BP 结束后：格式化的阵容名单（替换"我方/对方"）"""
        match_key = f"{match.league}_{match.stage}_{match.round}"
        notified_games = self._state.bp_round_notice.get(match_key, [])
        
        if not match.games:
            return
        
        for game in match.games:
            if game.game_no in notified_games:
                continue
            
            # 检查 BP 是否完成（这里简化判断：有 BP 数据即认为完成）
            if hasattr(game, 'bp') and game.bp:
                team_a = game.blue_team or (match.teams[0] if match.teams else "蓝方")
                team_b = game.red_team or (match.teams[1] if len(match.teams) > 1 else "红方")
                
                text = formatter.format_match_bp(match)
                text = text.replace("我方", team_a).replace("对方", team_b)
                
                image_path = await img.render_match_bp(match)
                await self._broadcast(text, image_path)
                
                notified_games.append(game.game_no)
                self._state.bp_round_notice[match_key] = notified_games
                await self._persist_state()
                logger.info(f"[LoLNotifier] Sent BP for {match_key} game {game.game_no}")

    async def _check_round_finished(self, match: LeagueMatch, now: datetime) -> None:
        """每小局结束后：简要胜负 + 比赛战报 & 图片（替换"我方/对方"）"""
        match_key = f"{match.league}_{match.stage}_{match.round}"
        notified_games = self._state.post_round_notice.get(match_key, [])
        
        if not match.games:
            return
        
        for game in match.games:
            if game.game_no in notified_games:
                continue
            
            # 检查小局是否结束（有胜者即认为结束）
            if game.winner:
                team_a = game.blue_team or (match.teams[0] if match.teams else "蓝方")
                team_b = game.red_team or (match.teams[1] if len(match.teams) > 1 else "红方")
                
                text = formatter.format_post_match_summary(match, report="战报数据尚未接入", image_url=None)
                
                image_path = await img.render_match_result(match)
                await self._broadcast(text, image_path)
                
                notified_games.append(game.game_no)
                self._state.post_round_notice[match_key] = notified_games
                await self._persist_state()
                logger.info(f"[LoLNotifier] Sent round result for {match_key} game {game.game_no}")

    async def _check_match_finished(self, match: LeagueMatch, now: datetime) -> None:
        """比赛结束后：最终比分 + MVP / FMVP + B站回放视频 + 颁奖采访"""
        match_key = f"{match.league}_{match.stage}_{match.round}_final"
        if self._state.post_round_notice.get(match_key):
            return
        
        # 检查比赛是否完全结束（所有小局都有结果）
        if match.games and all(g.winner for g in match.games):
            # 获取 B 站回放
            replays = await bilibili.fetch_bilibili_replays()
            replay_text = "\n\n📺 回放视频：\n" + "\n".join([r.get("title", "") + " " + r.get("url", "") for r in replays[:1]]) if replays else ""
            
            text = formatter.format_match_result(match)
            text += "\n\n🏆 MVP / FMVP 数据尚未接入"
            text += replay_text
            
            image_path = await img.render_match_result(match)
            await self._broadcast(text, image_path)
            
            self._state.post_round_notice[match_key] = [1]
            await self._persist_state()
            logger.info(f"[LoLNotifier] Sent match final result for {match_key}")

    async def _check_bilibili_feeds(self) -> None:
        """B站多账号统一推送：遍历所有账号，按 per-type toggle 拉取视频/图文动态。"""
        if not is_any_bilibili_push_enabled(self._config):
            return

        try:
            for account in BILIBILI_ACCOUNTS:
                uid = account["uid"]
                key = account["key"]
                name = account["name"]

                # ── 视频 ──
                if is_bilibili_push_enabled(self._config, key, "video"):
                    await self._check_bilibili_videos_for_uid(uid, key, name)

                # ── 图文动态 ──
                if is_bilibili_push_enabled(self._config, key, "article"):
                    await self._check_bilibili_dynamics_for_uid(uid, key, name)

                # ── 直播 ──
                if is_bilibili_push_enabled(self._config, key, "live"):
                    await self._check_bilibili_live_for_uid(uid, key, name)
        except Exception as e:
            logger.error(f"[LoLNotifier] Error checking bilibili feeds: {e}")

    async def _check_bilibili_videos_for_uid(self, uid: str, key: str, name: str) -> None:
        """拉取指定 UID 的视频投稿并推送"""
        try:
            updates = await bilibili.fetch_bilibili_updates(uid)
            if not updates:
                return

            seen = self._state.bilibili_video_seen.get(uid, set())

            # 首次运行仅记录
            if not seen:
                for item in updates:
                    seen.add(item.get("bvid", ""))
                self._state.bilibili_video_seen[uid] = seen
                await self._persist_state()
                logger.info(f"[LoLNotifier] B站-{name}: first run, recorded {len(updates)} existing videos")
                return

            now_ts = int(datetime.now(timezone.utc).timestamp())
            new_items = []
            for item in updates:
                bvid = item.get("bvid", "")
                if not bvid or bvid in seen:
                    continue
                pubdate = item.get("pubdate", 0)
                if now_ts - pubdate > POLL_INTERVAL * 3:
                    continue
                new_items.append(item)
                seen.add(bvid)

            if new_items:
                self._state.bilibili_video_seen[uid] = seen
                text = formatter.format_bilibili_update(new_items, name)
                await self._broadcast(text, None)
                await self._persist_state()
                logger.info(f"[LoLNotifier] B站-{name}: sent {len(new_items)} video(s)")
        except Exception as e:
            logger.error(f"[LoLNotifier] Error checking B站 videos for {name}: {e}")

    async def _check_bilibili_dynamics_for_uid(self, uid: str, key: str, name: str) -> None:
        """拉取指定 UID 的图文动态（含视频转发）并推送"""
        try:
            dynamics = await bilibili.fetch_bilibili_dynamics(uid)
            if not dynamics:
                return

            seen = self._state.bilibili_dynamic_seen.get(uid, set())

            # 首次运行仅记录
            if not seen:
                for item in dynamics:
                    seen.add(item.get("dynamic_id", ""))
                self._state.bilibili_dynamic_seen[uid] = seen
                await self._persist_state()
                logger.info(f"[LoLNotifier] B站-{name}: first run, recorded {len(dynamics)} existing dynamics")
                return

            new_items = []
            for item in dynamics:
                dyn_id = item.get("dynamic_id", "")
                if not dyn_id or dyn_id in seen:
                    continue
                new_items.append(item)
                seen.add(dyn_id)

            if new_items:
                self._state.bilibili_dynamic_seen[uid] = seen
                text = formatter.format_bilibili_bp_update(new_items)
                await self._broadcast(text, None)
                await self._persist_state()
                logger.info(f"[LoLNotifier] B站-{name}: sent {len(new_items)} dynamic(s)")
        except Exception as e:
            logger.error(f"[LoLNotifier] Error checking B站 dynamics for {name}: {e}")

    async def _check_bilibili_live_for_uid(self, uid: str, key: str, name: str) -> None:
        """检测指定 UID 的直播开播/下播状态并推送。"""
        try:
            lives = await bilibili.fetch_bilibili_live_status(uid)
            has_notified = self._state.bilibili_live_state.get(uid, False)

            if lives:
                live = lives[0]
                if live.get("live_status") == 0:
                    # 下播
                    if has_notified:
                        text = f"⏹️ **{name}** 直播已结束\n  ▸ {live.get('title', '')}"
                        await self._broadcast(text, None)
                        self._state.bilibili_live_state[uid] = False
                        await self._persist_state()
                        logger.info(f"[LoLNotifier] B站-{name}: live ended")
                elif live.get("live_status") == 1 and not has_notified:
                    # 开播
                    text = (
                        f"🔴 **{name}** 开播了！\n"
                        f"  ▸ {live.get('title', '')}\n"
                        f"  ▸ 人气 {live.get('online', 0):,}\n"
                        f"  ▸ {live.get('url', '')}"
                    )
                    await self._broadcast(text, None)
                    self._state.bilibili_live_state[uid] = True
                    await self._persist_state()
                    logger.info(f"[LoLNotifier] B站-{name}: live started")
            else:
                # 无直播间或未开播
                if has_notified:
                    self._state.bilibili_live_state[uid] = False
                    await self._persist_state()
        except Exception as e:
            logger.error(f"[LoLNotifier] Error checking B站 live for {name}: {e}")

    # ── 微博赛前海报 ──

    async def _check_weibo_posters(self) -> None:
        """微博 英雄联盟赛事 (UID 6537214902)：检测 LPL+预告 赛前海报并推送"""
        if not is_weibo_poster_push_enabled(self._config):
            return

        try:
            uids = get_weibo_uids(self._config)
            if not uids:
                return

            posters = await weibo.fetch_weibo_posters(uids)
            if not posters:
                return

            new_posters = []
            for post in posters:
                post_id = str(post.get("id") or post.get("mid", ""))
                if post_id and post_id not in self._state.weibo_updates:
                    new_posters.append(post)
                    self._state.weibo_updates.add(post_id)

            if new_posters:
                text = formatter.format_weibo_poster(new_posters)
                await self._broadcast(text, None)
                await self._persist_state()
                logger.info(f"[LoLNotifier] Sent {len(new_posters)} weibo poster(s)")
        except Exception as e:
            logger.error(f"[LoLNotifier] Error checking weibo posters: {e}")

    # ── 赛事节点 ──

    async def _check_live_matches(self) -> None:
        """实时比赛轮询：检测正在进行中的比赛，有比分变化时推送"""
        try:
            result = await api.get_live_matches()
            if not result.ok or not result.value:
                return

            live_matches: list[LiveMatch] = result.value
            for lm in live_matches:
                # 只推送有正在进行中的局的比赛
                active_games = [g for g in lm.games if g.state == "in_progress"]
                if not active_games:
                    continue

                # 构建状态键
                match_key = lm.match_id or f"{lm.league}_{lm.match_name}"
                prev_key = f"live_last_{match_key}"

                # 计算摘要指纹（比分+总击杀）
                summary = f"{lm.score}|{sum(g.blue_kills + g.red_kills for g in lm.games)}"

                prev_summary = self._state.elimination_updates.get(prev_key, "")
                if summary == prev_summary:
                    continue  # 无变化,不推送

                self._state.elimination_updates[prev_key] = summary
                await self._persist_state()

                text = formatter.format_live_match(lm)
                await self._broadcast(text, None)
                logger.info(f"[LoLNotifier] Sent live update for {match_key}: {summary}")
        except Exception as e:
            logger.error(f"[LoLNotifier] Error checking live matches: {e}")

    # ── 赛事节点 ──

    async def _check_daily_schedule(self, now_utc: datetime) -> None:
        """每天北京时间指定时间推送当日赛程（仅 LPL/LCK/MSI/Worlds）。"""
        beijing_tz = timezone(timedelta(hours=8))
        beijing_now = now_utc.astimezone(beijing_tz)
        today_str = beijing_now.strftime("%Y-%m-%d")

        # 检查今天是否已推送
        if self._state.daily_schedule_sent_date == today_str:
            return

        # 检查是否到了推送时间
        push_time_str = get_schedule_push_time(self._config)  # e.g. "08:00"
        try:
            push_hour, push_minute = map(int, push_time_str.split(":"))
        except ValueError:
            push_hour, push_minute = 8, 0

        # 只在推送时间 ± 2.5 分钟窗口内触发（5分钟轮询间隔的一半）
        current_minutes = beijing_now.hour * 60 + beijing_now.minute
        push_minutes = push_hour * 60 + push_minute
        if abs(current_minutes - push_minutes) > 2:
            return

        # 获取目标联赛列表
        leagues = get_schedule_leagues(self._config)  # ["lpl","lck","msi","worlds"]

        try:
            result = await api.get_daily_schedule_multi_league(leagues)
            if not result.ok:
                logger.warning(f"[LoLNotifier] Daily schedule fetch failed: {result.error}")
                return

            matches = result.value or []
            if not matches:
                text = "📅 今日无赛程，好好休息一下吧~"
                await self._broadcast(text, None)
                logger.info("[LoLNotifier] Daily schedule: no matches today")
            else:
                text = formatter.format_daily_schedule(matches)
                image_path = await img.render_daily_schedule(matches) if self._image_mode else None
                await self._broadcast(text, image_path)
                logger.info(f"[LoLNotifier] Daily schedule: sent {len(matches)} matches for {today_str}")

            self._state.daily_schedule_sent_date = today_str
            await self._persist_state()
        except Exception as e:
            logger.error(f"[LoLNotifier] Error in daily schedule check: {e}", exc_info=True)

    async def _check_pre_match_10min(self, now_utc: datetime) -> None:
        """赛前 10 分钟推送预告。"""
        leagues = get_schedule_leagues(self._config)

        try:
            result = await api.get_daily_schedule_multi_league(leagues)
            if not result.ok or not result.value:
                return

            beijing_tz = timezone(timedelta(hours=8))

            for match in result.value:
                if not match.match_id or match.match_id in self._state.pre_match_10min_notified:
                    continue

                # 解析比赛时间
                try:
                    match_dt_str = f"{match.start_date}T{match.start_time}"
                    match_dt = datetime.strptime(match_dt_str, "%Y-%m-%dT%H:%M")
                    match_dt = match_dt.replace(tzinfo=beijing_tz)
                except (ValueError, TypeError):
                    continue

                # 距现在还有多少秒
                time_until = (match_dt - now_utc).total_seconds()

                # 在比赛开始前 8~12 分钟窗口内触发（兼容 5 分钟轮询间隔）
                if 480 <= time_until <= 720:
                    text = formatter.format_pre_match_alert(match)
                    image_path = await img.render_pre_match_alert(match) if self._image_mode else None
                    await self._broadcast(text, image_path)

                    self._state.pre_match_10min_notified.add(match.match_id)
                    await self._persist_state()
                    logger.info(
                        f"[LoLNotifier] Pre-match alert: {match.teams} "
                        f"({match.match_name}) in {int(time_until // 60)}min"
                    )
        except Exception as e:
            logger.error(f"[LoLNotifier] Error in pre-match check: {e}", exc_info=True)

    async def _check_elimination_updates(self) -> None:
        """败者组/淘汰赛关键节点：晋级/淘汰情况 + 后续对阵"""
        try:
            # TODO: 实现淘汰赛节点检测逻辑
            pass
        except Exception as e:
            logger.error(f"[LoLNotifier] Error checking elimination: {e}")
