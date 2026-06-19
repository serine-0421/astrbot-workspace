"""Riot API Key manager with auto-refresh capability.

Riot Developer API keys expire every 24 hours. This module:
- Loads key from config / env var / local cache
- Validates key periodically via a test request
- Auto-refreshes using Riot account credentials (if provided)
- Caches the key locally to survive restarts

Riot 开发者 API Key 每 24 小时过期，本模块提供自动刷新能力。

Usage:
    from .api_key_manager import get_key_manager

    mgr = get_key_manager()
    await mgr.initialize(config)   # 插件启动时
    key = await mgr.get_key()       # 获取有效 key
    status = await mgr.check_status()  # 检查状态
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from astrbot.api import logger

# ── 常量 ──

# Riot 认证 API
_AUTH_URL = "https://auth.riotgames.com/api/v1/authorization"
# Riot 开发者门户 API（获取/刷新 Key）
_DEV_PORTAL_KEY_URL = "https://developer.riotgames.com/api/v1/keys/apikey"
# 验证 Key 有效性的测试端点
_VALIDATE_URL = "https://esports-api.lolesports.com/persisted/gw/getLeagues"

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

# Key 过期前多久开始尝试刷新（秒）
_REFRESH_BEFORE_EXPIRY = 3600  # 1 小时
# 最小刷新间隔（秒），防止频繁重试
_MIN_REFRESH_INTERVAL = 300  # 5 分钟
# 本地缓存文件
_KEY_CACHE_FILE = "riot_api_key.json"


class ApiKeyManager:
    """Riot API Key 生命周期管理器。"""

    def __init__(self) -> None:
        self._key: str = ""
        self._key_obtained_at: float = 0.0  # 获取 key 的时间戳
        self._last_validated_at: float = 0.0
        self._last_refresh_attempt: float = 0.0
        self._is_valid: bool = False
        self._config: dict[str, Any] = {}
        self._cache_path: Path | None = None

    # ── 初始化 ──

    async def initialize(self, config: dict[str, Any] | None = None, data_dir: str = "data") -> None:
        """初始化 Key 管理器，按优先级加载 Key。

        优先级: 环境变量 RIOT_API_KEY > 配置文件 riot_api_key > 本地缓存 > 自动刷新
        """
        self._config = config or {}

        # 确定缓存文件路径
        cache_dir = Path(data_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_path = cache_dir / _KEY_CACHE_FILE

        # 1. 环境变量（最高优先级）
        env_key = os.environ.get("RIOT_API_KEY", "").strip()
        if env_key:
            self._key = env_key
            self._key_obtained_at = time.time()
            logger.info("[ApiKeyManager] 使用环境变量 RIOT_API_KEY")
            await self._validate()
            return

        # 2. 配置文件
        config_key = str(self._config.get("riot_api_key", "")).strip()
        if config_key:
            self._key = config_key
            self._key_obtained_at = time.time()
            logger.info("[ApiKeyManager] 使用配置文件中的 riot_api_key")
            await self._validate()
            if self._is_valid:
                return

        # 3. 本地缓存
        cached = self._load_cache()
        if cached:
            self._key = cached.get("key", "")
            self._key_obtained_at = cached.get("obtained_at", 0.0)
            if self._key:
                logger.info("[ApiKeyManager] 使用本地缓存 Key")
                await self._validate()
                if self._is_valid:
                    return

        # 4. 尝试自动刷新
        if self._has_credentials():
            logger.info("[ApiKeyManager] 尝试使用 Riot 账号自动获取 Key...")
            if await self._try_refresh():
                return

        logger.warning(
            "[ApiKeyManager] 未找到有效 API Key！\n"
            "  请使用 /lol apikey <key> 设置，或设置环境变量 RIOT_API_KEY。\n"
            "  Riot Dev Key 申请: https://developer.riotgames.com/"
        )

    # ── 公共 API ──

    async def get_key(self) -> str:
        """获取当前有效的 API Key。如果过期则尝试刷新。"""
        if self._is_expired() and self._has_credentials():
            await self._try_refresh()
        return self._key

    async def set_key(self, key: str) -> bool:
        """手动设置 API Key 并验证。"""
        self._key = key.strip()
        self._key_obtained_at = time.time()
        await self._validate()
        if self._is_valid:
            self._save_cache()
            logger.info("[ApiKeyManager] 手动设置 Key 成功并通过验证")
        else:
            logger.warning("[ApiKeyManager] 手动设置 Key 未通过验证，可能无效")
        return self._is_valid

    async def check_status(self) -> dict[str, Any]:
        """返回 Key 状态信息。"""
        if not self._key:
            return {
                "status": "missing",
                "message": "未设置 API Key。请使用 /lol apikey <key> 设置。\n"
                           "获取 Key: https://developer.riotgames.com/",
            }

        if self._last_validated_at == 0:
            await self._validate()

        now = time.time()
        age_hours = (now - self._key_obtained_at) / 3600 if self._key_obtained_at else 0
        hours_left = max(0, 24 - age_hours)

        return {
            "status": "valid" if self._is_valid else "invalid",
            "message": (
                f"✅ API Key 有效\n"
                f"  已使用: {age_hours:.1f} 小时\n"
                f"  剩余约: {hours_left:.1f} 小时\n"
                f"  Key 尾号: ...{self._key[-6:] if len(self._key) > 6 else self._key}"
            ) if self._is_valid else "❌ API Key 无效或已过期",
            "valid": self._is_valid,
            "age_hours": round(age_hours, 1),
            "hours_left": round(hours_left, 1),
        }

    async def force_refresh(self) -> dict[str, Any]:
        """强制刷新 API Key（需要配置 Riot 账号密码）。"""
        if not self._has_credentials():
            return {
                "success": False,
                "message": "未配置 Riot 账号密码。\n"
                           "请在插件配置中设置 riot_username 和 riot_password。",
            }

        logger.info("[ApiKeyManager] 强制刷新 Key...")
        success = await self._try_refresh()
        if success:
            return {"success": True, "message": "✅ API Key 刷新成功！"}
        return {
            "success": False,
            "message": "❌ 自动刷新失败。\n"
                       "可能原因: 账号密码错误 / 需要二次验证 / 网络问题。\n"
                       "请手动获取: https://developer.riotgames.com/",
        }

    # ── 内部方法 ──

    def _has_credentials(self) -> bool:
        """检查是否配置了 Riot 登录凭证。"""
        username = str(self._config.get("riot_username", "")).strip()
        password = str(self._config.get("riot_password", "")).strip()
        return bool(username and password)

    def _is_expired(self) -> bool:
        """检查 Key 是否接近过期（>23小时）。"""
        if not self._key or not self._key_obtained_at:
            return True
        age = time.time() - self._key_obtained_at
        return age > (86400 - _REFRESH_BEFORE_EXPIRY)

    async def _validate(self) -> bool:
        """通过测试请求验证 Key 有效性。"""
        if not self._key:
            self._is_valid = False
            return False

        now = time.time()
        # 避免过于频繁验证
        if now - self._last_validated_at < 60 and self._is_valid:
            return self._is_valid

        self._last_validated_at = now

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    _VALIDATE_URL,
                    params={"hl": "en-US"},
                    headers={
                        "User-Agent": _USER_AGENT,
                        "x-api-key": self._key,
                    },
                )
                # 200 = 有效, 403 = 无效/过期
                self._is_valid = resp.status_code == 200

                if resp.status_code == 403:
                    logger.warning("[ApiKeyManager] API Key 验证失败 (403)，可能已过期")
                elif resp.status_code == 429:
                    logger.warning("[ApiKeyManager] Rate limited during validation")
                    self._is_valid = True  # 限流不代表 key 无效

        except Exception as e:
            logger.warning(f"[ApiKeyManager] Key 验证请求异常: {e}")
            # 网络异常时保守认为有效
            self._is_valid = True

        return self._is_valid

    async def _try_refresh(self) -> bool:
        """尝试通过 Riot 账号自动获取新 Key。"""
        now = time.time()
        if now - self._last_refresh_attempt < _MIN_REFRESH_INTERVAL:
            logger.info("[ApiKeyManager] 距上次刷新尝试不足 5 分钟，跳过")
            return False

        self._last_refresh_attempt = now

        username = str(self._config.get("riot_username", "")).strip()
        password = str(self._config.get("riot_password", "")).strip()

        if not username or not password:
            return False

        try:
            async with httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers={"User-Agent": _USER_AGENT},
            ) as client:
                # Step 1: Riot 账号认证
                auth_payload = {
                    "type": "auth",
                    "username": username,
                    "password": password,
                    "persistLogin": True,
                }

                auth_resp = await client.put(
                    _AUTH_URL,
                    json=auth_payload,
                )

                if auth_resp.status_code != 200:
                    logger.warning(
                        f"[ApiKeyManager] Riot 认证失败: HTTP {auth_resp.status_code}"
                    )
                    return False

                auth_data = auth_resp.json()

                # 检查是否需要二次验证
                if auth_data.get("type") == "multifactor":
                    logger.warning(
                        "[ApiKeyManager] Riot 账号需要二次验证（2FA），"
                        "无法自动刷新 Key。请手动获取。"
                    )
                    return False

                # 检查认证是否成功
                if auth_data.get("type") != "response":
                    error_msg = auth_data.get("error", "未知错误")
                    logger.warning(f"[ApiKeyManager] Riot 认证返回异常: {error_msg}")
                    return False

                access_token = (
                    auth_data.get("success", {}).get("access_token", "")
                    or auth_data.get("response", {}).get("parameters", {}).get("uri", "")
                )

                if "access_token" not in str(auth_data):
                    logger.warning(
                        "[ApiKeyManager] 认证响应中未找到 access_token，"
                        "可能需要人机验证（CAPTCHA）"
                    )
                    return False

                # Step 2: 访问开发者门户获取/刷新 Key
                logger.info("[ApiKeyManager] Riot 认证成功，正在获取 API Key...")

                # 先获取当前 key 信息
                try:
                    key_info = await client.get(_DEV_PORTAL_KEY_URL)
                    if key_info.status_code == 200:
                        key_data = key_info.json()
                        new_key = key_data.get("apiKey", key_data.get("key", ""))
                        if new_key:
                            self._key = new_key
                            self._key_obtained_at = time.time()
                            self._save_cache()
                            await self._validate()
                            logger.info(
                                f"[ApiKeyManager] ✅ 成功获取 API Key: ...{new_key[-6:]}"
                            )
                            return True
                except Exception:
                    pass

                # 尝试重新生成 key (PUT)
                try:
                    regen_resp = await client.put(_DEV_PORTAL_KEY_URL)
                    if regen_resp.status_code == 200:
                        regen_data = regen_resp.json()
                        new_key = regen_data.get("apiKey", regen_data.get("key", ""))
                        if new_key:
                            self._key = new_key
                            self._key_obtained_at = time.time()
                            self._save_cache()
                            await self._validate()
                            logger.info(
                                f"[ApiKeyManager] ✅ 成功刷新 API Key: ...{new_key[-6:]}"
                            )
                            return True
                except Exception:
                    pass

                logger.warning("[ApiKeyManager] 认证成功但无法获取 API Key")
                return False

        except httpx.RequestError as e:
            logger.error(f"[ApiKeyManager] 刷新请求网络错误: {e}")
            return False
        except Exception as e:
            logger.error(f"[ApiKeyManager] 刷新异常: {e}", exc_info=True)
            return False

    # ── 缓存管理 ──

    def _load_cache(self) -> dict[str, Any] | None:
        """从本地文件加载缓存的 Key。"""
        if not self._cache_path or not self._cache_path.exists():
            return None
        try:
            with open(self._cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("key"):
                return data
        except Exception as e:
            logger.debug(f"[ApiKeyManager] 读取缓存失败: {e}")
        return None

    def _save_cache(self) -> None:
        """保存 Key 到本地缓存文件。"""
        if not self._cache_path or not self._key:
            return
        try:
            with open(self._cache_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "key": self._key,
                        "obtained_at": self._key_obtained_at,
                        "saved_at": time.time(),
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        except Exception as e:
            logger.debug(f"[ApiKeyManager] 保存缓存失败: {e}")


# ── 全局单例 ──

_manager: ApiKeyManager | None = None


def get_key_manager() -> ApiKeyManager:
    """获取全局 Key 管理器单例。"""
    global _manager
    if _manager is None:
        _manager = ApiKeyManager()
    return _manager
