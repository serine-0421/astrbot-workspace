"""Background scheduler for LoL notifications."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from astrbot.api import logger
from astrbot.api.message.components import Image, MessageChain, Plain

from . import image_renderer as img
from .fetcher import api as fetcher_api
from .fetcher import bilibili, weibo
from .formatter import message as formatter
from .models import Failure, LeagueMatch, Success
from .state import NotificationState, default_state

if TYPE_CHECKING:
    from astrbot.api import AstrBotConfig
    from astrbot.api.star import Star
    from astrbot.core.star.context import Context


POLL_INTERVAL = 60
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
        img.configure(config)

    @property
    def _image_mode(self) -> bool:
        return bool(self._config.get("enable_image_render", False)) if self._config else False

    def start(self) -> None:
        if self._task is None or self._task.done():
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
            "bilibili_updates": list(self._state.bilibili_updates),
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
        """主推送检查逻辑：按时机触发各类通知"""
        now = datetime.now(timezone.utc)
        
        # 1. 检查 B 站官号更新
        await self._check_bilibili_updates()
        
        # 2. 检查微博官号更新
        await self._check_weibo_updates()
        
        # 2. 获取赛程数据
        schedule_result = await fetcher_api.get_schedule("lck", "regular", "current")
        if isinstance(schedule_result, Failure):
            return
        
        matches = schedule_result.value if schedule_result.value else []
        if not matches:
            return
        
        # 3. 检查各个推送时机
        for match in matches:
            await self._check_24h_before_match(match, now)
            await self._check_30min_before_match(match, now)
            await self._check_bp_finished(match, now)
            await self._check_round_finished(match, now)
            await self._check_match_finished(match, now)
        
        # 4. 检查淘汰赛关键节点
        await self._check_elimination_updates()

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
                posters = await weibo.fetch_weibo_posters()
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
                posters = await weibo.fetch_weibo_posters()
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
        """比赛结束后：最终比分 + MVP / FMVP + B站官号回放视频 + 颁奖采访"""
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

    async def _check_bilibili_updates(self) -> None:
        """B站官号更新：全量自动推送所有动态/视频"""
        try:
            updates = await bilibili.fetch_bilibili_updates()
            if not updates:
                return
            
            new_updates = []
            for item in updates:
                item_id = item.get("id") or item.get("bvid") or item.get("dynamic_id", "")
                if item_id and item_id not in self._state.bilibili_updates:
                    new_updates.append(item)
                    self._state.bilibili_updates.add(item_id)
            
            if new_updates:
                text = formatter.format_bilibili_update(new_updates)
                await self._broadcast(text, None)
                await self._persist_state()
                logger.info(f"[LoLNotifier] Sent {len(new_updates)} bilibili updates")
        except Exception as e:
            logger.error(f"[LoLNotifier] Error checking bilibili: {e}")

    async def _check_weibo_updates(self) -> None:
        """微博官号更新：根据白名单/屏蔽词过滤后推送原创微博"""
        try:
            posts = await weibo.fetch_weibo_announcements()
            if not posts:
                return

            new_posts = []
            for post in posts:
                post_id = str(post.get("id") or post.get("mid", ""))
                if post_id and post_id not in self._state.weibo_updates:
                    new_posts.append(post)
                    self._state.weibo_updates.add(post_id)

            if new_posts:
                lines = ["📢 微博官号更新\n"]
                for post in new_posts:
                    lines.append(f"• {post.get('text', '').strip()[:80]}")
                    if post.get("url"):
                        lines.append(f"  {post['url']}")
                await self._broadcast("\n".join(lines), None)
                await self._persist_state()
                logger.info(f"[LoLNotifier] Sent {len(new_posts)} weibo updates")
        except Exception as e:
            logger.error(f"[LoLNotifier] Error checking weibo: {e}")

    async def _check_elimination_updates(self) -> None:
        """败者组/淘汰赛关键节点：晋级/淘汰情况 + 后续对阵"""
        try:
            # TODO: 实现淘汰赛节点检测逻辑
            # 这里需要从 API 获取淘汰赛进度数据
            pass
        except Exception as e:
            logger.error(f"[LoLNotifier] Error checking elimination: {e}")
