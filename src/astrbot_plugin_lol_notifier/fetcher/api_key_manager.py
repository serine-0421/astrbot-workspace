"""Riot Developer API Key 自动刷新管理器。

使用内置 Riot 账号（serine0421）自动登录刷新 API Key，插件使用方无需手动配置。
优先级：环境变量 RIOT_API_KEY > 配置文件 riot_api_key > 自动登录刷新 > 本地缓存

用法:
    from .api_key_manager import get_key_manager
    mgr = get_key_manager()
    await mgr.initialize(config, data_dir="data")
    key = await mgr.get_key()
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any

import httpx

from astrbot.api import logger

# ── 内置 Riot 账号（插件作者提供） ──
_BUILTIN_USERNAME = "serine0421"
_BUILTIN_PASSWORD = "Adastra0421"

# ── 常量 ──
_AUTH_URL = "https://auth.riotgames.com/api/v1/authorization"
_DEV_PORTAL = "https://developer.riotgames.com"
_DEV_KEY_API = f"{_DEV_PORTAL}/api/v1/keys/apikey"
_VALIDATE_URL = "https://esports-api.lolesports.com/persisted/gw/getLeagues"

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

_KEY_CACHE_FILE = "riot_api_key.json"
_REFRESH_BEFORE_EXPIRY = 3600      # 过期前 1h 刷新
_MIN_REFRESH_INTERVAL = 300        # 最小刷新间隔 5min

# ── 全局单例 ──
_key_manager: ApiKeyManager | None = None


def get_key_manager() -> "ApiKeyManager":
    global _key_manager
    if _key_manager is None:
        _key_manager = ApiKeyManager()
    return _key_manager


class ApiKeyManager:
    """Riot API Key 生命周期管理器。自动使用内置账号刷新。"""

    def __init__(self) -> None:
        self._key: str = ""
        self._key_obtained_at: float = 0.0
        self._last_refresh_attempt: float = 0.0
        self._is_valid: bool = False
        self._last_error: str = ""
        self._config: dict[str, Any] = {}
        self._cache_path: Path | None = None
        self._next_refresh_task: asyncio.Task | None = None

    # ═══════════════════════════════════════════════════════
    # 初始化
    # ═══════════════════════════════════════════════════════

    async def initialize(
        self, config: dict[str, Any] | None = None, data_dir: str = "data"
    ) -> None:
        """按优先级加载：环境变量 > 配置文件 > 自动刷新 > 缓存。"""
        self._config = config or {}
        self._cache_path = Path(data_dir) / _KEY_CACHE_FILE
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)

        # 1) 环境变量 RIOT_API_KEY
        env_key = os.environ.get("RIOT_API_KEY", "").strip()
        if env_key:
            logger.info("[KeyManager] 使用环境变量 RIOT_API_KEY")
            self._key = env_key
            self._key_obtained_at = time.time()
            await self._validate()
            return

        # 2) 配置文件 riot_api_key
        config_key = str(self._config.get("riot_api_key", "")).strip()
        if config_key:
            logger.info("[KeyManager] 使用配置文件 riot_api_key")
            self._key = config_key
            self._key_obtained_at = time.time()
            if await self._validate():
                return

        # 3) 本地缓存
        cached = self._load_cache()
        if cached:
            self._key = cached.get("key", "")
            self._key_obtained_at = cached.get("obtained_at", 0)
            if self._key and await self._validate():
                logger.info("[KeyManager] 使用缓存 Key")
                self._schedule_refresh()
                return
            logger.info("[KeyManager] 缓存 Key 已失效")

        # 4) 自动登录刷新（使用内置账号）
        logger.info("[KeyManager] 使用内置账号自动刷新...")
        await self._try_auto_refresh()

    # ═══════════════════════════════════════════════════════
    # 公共 API
    # ═══════════════════════════════════════════════════════

    async def get_key(self) -> str:
        """获取当前 Key，过期自动刷新。"""
        if self._should_refresh():
            await self._try_auto_refresh()
        return self._key

    async def set_key(self, key: str) -> bool:
        """手动设置 Key（用户命令）。"""
        key = key.strip()
        if not key or len(key) < 10:
            self._last_error = "Key 格式无效（至少 10 个字符）"
            return False
        self._key = key
        self._key_obtained_at = time.time()
        if await self._validate():
            self._save_cache()
            logger.info("[KeyManager] 手动 Key 验证通过")
            return True
        self._last_error = "Key 验证失败，请检查是否正确"
        return False

    async def check_status(self) -> dict[str, Any]:
        """返回 Key 状态详情。"""
        if not self._key:
            return {
                "status": "no_key",
                "message": (
                    "⚠️ 尚未获取到 API Key，正在尝试自动刷新...\n\n"
                    "如持续失败，可手动设置: /lol apikey <你的key>\n"
                    "获取 Key: https://developer.riotgames.com/"
                ),
                "valid": False,
            }

        if not self._is_valid:
            await self._validate()

        age_hours = (time.time() - self._key_obtained_at) / 3600 if self._key_obtained_at else 0
        remaining_hours = max(0, 24 - age_hours)
        masked = self._key[:8] + "****" + self._key[-4:] if len(self._key) > 12 else "****"
        source = "手动设置" if self._config.get("riot_api_key") else "自动刷新"

        if self._is_valid:
            return {
                "status": "valid",
                "message": (
                    f"✅ Key 有效\n"
                    f"  {masked}\n"
                    f"  已用: {age_hours:.1f}h / 剩余: {remaining_hours:.1f}h\n"
                    f"  来源: {source}"
                ),
                "valid": True,
            }
        return {
            "status": "invalid",
            "message": (
                f"❌ Key 无效\n"
                f"  错误: {self._last_error or '验证未通过'}\n"
                f"  建议: /lol apikey <你的key>"
            ),
            "valid": False,
        }

    async def force_refresh(self) -> dict[str, Any]:
        """强制刷新，忽略间隔限制。"""
        self._last_refresh_attempt = 0
        ok = await self._try_auto_refresh()
        status = await self.check_status()
        status["refreshed"] = ok
        return status

    # ═══════════════════════════════════════════════════════
    # 自动刷新
    # ═══════════════════════════════════════════════════════

    async def _try_auto_refresh(self) -> bool:
        """使用内置 Riot 账号登录获取 API Key。"""
        now = time.time()
        if now - self._last_refresh_attempt < _MIN_REFRESH_INTERVAL and self._is_valid:
            return False
        self._last_refresh_attempt = now

        # 优先用配置文件中的账号，否则用内置账号
        username = str(self._config.get("riot_username", "")).strip() or _BUILTIN_USERNAME
        password = str(self._config.get("riot_password", "")).strip() or _BUILTIN_PASSWORD

        logger.info(f"[KeyManager] 正在登录 Riot ({username})...")

        try:
            async with httpx.AsyncClient(timeout=45.0, follow_redirects=False) as client:
                # Step 1: Riot SSO 认证
                auth_resp = await client.put(
                    _AUTH_URL,
                    json={
                        "type": "auth",
                        "username": username,
                        "password": password,
                        "remember": True,
                        "language": "en_US",
                    },
                    headers={
                        "User-Agent": _USER_AGENT,
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                )
                auth_data = auth_resp.json()
                auth_type = auth_data.get("type", "")

                if auth_type == "error":
                    err = auth_data.get("error", "unknown")
                    logger.warning(f"[KeyManager] 登录错误: {err}")
                    if "rate" in str(err).lower():
                        self._last_error = "Riot 登录频率限制，请稍后自动重试"
                    elif "captcha" in str(auth_data).lower():
                        self._last_error = "Riot 需要人机验证，自动登录暂不可用。可手动设置 Key"
                    else:
                        self._last_error = f"Riot 登录失败: {err}"
                    return False

                if auth_type == "multifactor":
                    self._last_error = "Riot 账号需要 2FA，自动登录不可用。请手动设置 Key"
                    logger.warning("[KeyManager] 需要 2FA")
                    return False

                if auth_type != "response":
                    self._last_error = f"未知认证响应: {auth_type}"
                    logger.warning(f"[KeyManager] 未知响应类型: {auth_type}")
                    return False

                # Step 2: 从响应中提取 access_token
                access_token = self._extract_token(auth_data, auth_resp)

                if not access_token:
                    self._last_error = "认证成功但未获取到 token，可能被 CAPTCHA 拦截"
                    logger.warning("[KeyManager] 无 access_token")
                    return False

                logger.info("[KeyManager] 获取到 access_token，正在取 API Key...")

                # Step 3: 用 token 从 Dev Portal 获取 Key
                new_key = await self._fetch_dev_key(client, access_token)
                if not new_key:
                    return False

                # Step 4: 验证并保存
                self._key = new_key
                self._key_obtained_at = time.time()
                if await self._validate():
                    self._save_cache()
                    self._schedule_refresh()
                    logger.info(f"[KeyManager] ✅ 自动刷新成功: {new_key[:8]}****")
                    self._last_error = ""
                    return True
                else:
                    self._last_error = "刷新后的 Key 验证失败"
                    return False

        except httpx.HTTPStatusError as e:
            self._last_error = f"HTTP {e.response.status_code}"
            logger.warning(f"[KeyManager] HTTP error: {e.response.status_code}")
            return False
        except Exception as e:
            self._last_error = f"网络异常: {e}"
            logger.warning(f"[KeyManager] 刷新异常: {e}")
            return False

    async def _fetch_dev_key(self, client: httpx.AsyncClient, access_token: str) -> str:
        """用 access_token 从 Dev Portal 获取/刷新 API Key。"""
        dev_headers = {
            "User-Agent": _USER_AGENT,
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}",
        }

        # 先 GET 现有 key
        try:
            resp = await client.get(_DEV_KEY_API, headers=dev_headers)
            if resp.status_code in (200, 201):
                data = resp.json()
                key = self._parse_key_from_response(data)
                if key:
                    return key
        except Exception:
            pass

        # PUT 刷新/创建 key
        try:
            resp = await client.put(_DEV_KEY_API, headers=dev_headers)
            if resp.status_code in (200, 201):
                data = resp.json()
                key = self._parse_key_from_response(data)
                if key:
                    return key
        except Exception:
            pass

        self._last_error = "Dev Portal 未返回有效 Key"
        return ""

    @staticmethod
    def _parse_key_from_response(data: Any) -> str:
        """从 Dev Portal 响应中提取 key 字符串。"""
        if isinstance(data, list) and data:
            return data[0].get("apiKey", data[0].get("key", ""))
        if isinstance(data, dict):
            return data.get("apiKey", data.get("key", ""))
        return ""

    def _extract_token(self, auth_data: dict, auth_resp) -> str:
        """从 Riot SSO 响应中提取 access_token。"""
        # 从 uri 参数中提取
        response = auth_data.get("response", {})
        parameters = response.get("parameters", {})
        uri = parameters.get("uri", "")

        if "access_token=" in uri:
            for part in uri.split("&"):
                if part.startswith("access_token="):
                    return part.split("=", 1)[1].split("#")[0]

        # 从 cookie 提取
        for cookie in auth_resp.cookies.jar:
            if cookie.name in ("access_token", "id_token"):
                return cookie.value

        return ""

    # ═══════════════════════════════════════════════════════
    # 验证 & 定时刷新
    # ═══════════════════════════════════════════════════════

    async def _validate(self) -> bool:
        """调用 getLeagues 验证 Key 有效性。"""
        if not self._key:
            return False
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
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("data", {}).get("leagues"):
                        self._is_valid = True
                        self._last_error = ""
                        return True
                    self._last_error = f"响应 200 但无 league 数据"
                elif resp.status_code == 403:
                    self._last_error = "HTTP 403: Key 无效或已过期"
                elif resp.status_code == 401:
                    self._last_error = "HTTP 401: Key 未授权"
                else:
                    self._last_error = f"HTTP {resp.status_code}"
        except Exception as e:
            self._last_error = f"验证异常: {e}"
        self._is_valid = False
        return False

    def _should_refresh(self) -> bool:
        """判断是否需要刷新（Key 超过 23h）。"""
        if not self._key:
            return True
        age = time.time() - self._key_obtained_at
        return age > 23 * 3600

    def _schedule_refresh(self) -> None:
        """安排定时后台刷新。"""
        if self._next_refresh_task and not self._next_refresh_task.done():
            self._next_refresh_task.cancel()
        self._next_refresh_task = asyncio.create_task(self._delayed_refresh())

    async def _delayed_refresh(self) -> None:
        """在 Key 过期前 1 小时自动刷新。"""
        await asyncio.sleep(23 * 3600)  # 23h 后刷新
        logger.info("[KeyManager] 定时刷新触发")
        await self._try_auto_refresh()

    # ═══════════════════════════════════════════════════════
    # 缓存
    # ═══════════════════════════════════════════════════════

    def _load_cache(self) -> dict[str, Any] | None:
        if not self._cache_path or not self._cache_path.exists():
            return None
        try:
            data = json.loads(self._cache_path.read_text(encoding="utf-8"))
            if data.get("key"):
                return data
        except Exception:
            pass
        return None

    def _save_cache(self) -> None:
        if not self._cache_path:
            return
        try:
            self._cache_path.write_text(
                json.dumps({
                    "key": self._key,
                    "obtained_at": self._key_obtained_at,
                }, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass
