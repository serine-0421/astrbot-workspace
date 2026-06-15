"""Background scheduler skeleton for LoL notifications."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from astrbot.api import logger

from . import image_renderer as img

if TYPE_CHECKING:
    from astrbot.api import AstrBotConfig
    from astrbot.api.star import Star
    from astrbot.core.star.context import Context


POLL_INTERVAL = 60


def _default_state() -> dict:
    return {"notified_rounds": {}}


class LoLScheduler:
    """Keeps subscription state and leaves room for future push logic."""

    def __init__(
        self, star: Star, context: Context, config: AstrBotConfig | None = None
    ) -> None:
        self.ctx = context
        self._star = star
        self._config = config
        self._subscribers: list[str] = []
        self._state: dict = _default_state()
        self._task: asyncio.Task | None = None
        self._loaded = False
        img.configure(config)

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
        self._state = await self._star.get_kv_data("lol_state", _default_state()) or _default_state()
        self._loaded = True

    async def _persist_subscribers(self) -> None:
        await self._star.put_kv_data("lol_subscribers", self._subscribers)

    async def _run(self) -> None:
        await self._load()
        while True:
            try:
                await asyncio.sleep(POLL_INTERVAL)
            except asyncio.CancelledError:
                break
