#!/usr/bin/env python3
"""Riot API Key 自动刷新脚本（独立运行，不依赖 AstrBot）。

用法:
  # 方式 1: 用账号密码尝试自动登录（可能被 CAPTCHA 拦截）
  python refresh_riot_key.py -u 你的Riot用户名 -p 你的Riot密码

  # 方式 2: 用浏览器 Cookie 刷新（最稳定，推荐）
  python refresh_riot_key.py --cookies-file cookies.json

  # 方式 3: 直接粘贴 Cookie JSON
  python refresh_riot_key.py --cookies-json '{"name":"value",...}'

  # 方式 4: 交互模式（一步步引导）
  python refresh_riot_key.py --interactive

  # 指定输出文件
  python refresh_riot_key.py -u xxx -p xxx -o ./data/riot_api_key.json

Cookie 获取方法:
  1. Chrome 打开 https://developer.riotgames.com/ 并登录
  2. F12 → Application → Cookies → developer.riotgames.com
  3. 逐个复制 Name 和 Value，或使用浏览器扩展导出
  4. 保存为 JSON 格式: {"cookie_name": "cookie_value", ...}

需要的 Cookie（至少包含以下之一）:
  - id_token 或 access_token  (Riot SSO 会话 token)
  - 或者完整的 developer.riotgames.com 下所有 cookie

依赖: pip install httpx
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    import httpx
except ImportError:
    print("请先安装 httpx: pip install httpx")
    sys.exit(1)

# ═══════════════════════════════════════════════
#  常量
# ═══════════════════════════════════════════════

_AUTH_URL = "https://auth.riotgames.com/api/v1/authorization"
_DEV_PORTAL = "https://developer.riotgames.com"
_DEV_KEY_API = f"{_DEV_PORTAL}/api/v1/keys/apikey"
_VALIDATE_URL = "https://esports-api.lolesports.com/persisted/gw/getLeagues"

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

# 颜色输出
_GREEN = "\033[92m"
_YELLOW = "\033[93m"
_RED = "\033[91m"
_CYAN = "\033[96m"
_RESET = "\033[0m"
_BOLD = "\033[1m"


def green(s: str) -> str:
    return f"{_GREEN}{s}{_RESET}"


def yellow(s: str) -> str:
    return f"{_YELLOW}{s}{_RESET}"


def red(s: str) -> str:
    return f"{_RED}{s}{_RESET}"


def cyan(s: str) -> str:
    return f"{_CYAN}{s}{_RESET}"


def bold(s: str) -> str:
    return f"{_BOLD}{s}{_RESET}"


# ═══════════════════════════════════════════════
#  核心逻辑
# ═══════════════════════════════════════════════


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Riot Developer API Key 自动刷新工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s -u MyRiotUser -p MyPassword
  %(prog)s --cookies-file cookies.json
  %(prog)s --cookies-json '{"id_token":"xxx"}'
  %(prog)s --interactive

Cookie 获取:
  1. Chrome 打开 https://developer.riotgames.com/ 登录
  2. F12 → Application → Cookies → developer.riotgames.com
  3. 逐个复制 Name 和 Value
        """,
    )
    p.add_argument("-u", "--username", help="Riot 账号用户名")
    p.add_argument("-p", "--password", help="Riot 账号密码")
    p.add_argument("--cookies-file", help="Cookie JSON 文件路径")
    p.add_argument("--cookies-json", help="直接传入 Cookie JSON 字符串")
    p.add_argument("-o", "--output", default="data/riot_api_key.json",
                   help="API Key 输出文件路径（默认 data/riot_api_key.json）")
    p.add_argument("--validate-only", action="store_true",
                   help="仅验证已有 Key，不刷新")
    p.add_argument("--key", help="手动指定 Key 进行验证")
    p.add_argument("-i", "--interactive", action="store_true",
                   help="交互模式")
    return p.parse_args()


def load_cookies(cookies_file: str | None, cookies_json: str | None) -> dict[str, str]:
    """从文件或 JSON 字符串加载 Cookie。"""
    if cookies_json:
        try:
            cookies = json.loads(cookies_json)
        except json.JSONDecodeError as e:
            print(red(f"✗ Cookie JSON 解析失败: {e}"))
            sys.exit(1)

        if isinstance(cookies, list):
            return {c.get("name", ""): c.get("value", "") for c in cookies if c.get("name")}
        if isinstance(cookies, dict):
            return {k: str(v) for k, v in cookies.items()}
        print(red("✗ Cookie 格式错误，需要 JSON 对象或数组"))
        sys.exit(1)

    if cookies_file:
        try:
            data = json.loads(Path(cookies_file).read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(red(f"✗ 读取 Cookie 文件失败: {e}"))
            sys.exit(1)

        if isinstance(data, list):
            return {c.get("name", ""): c.get("value", "") for c in data if c.get("name")}
        if isinstance(data, dict):
            return {k: str(v) for k, v in data.items()}

    return {}


# ── 策略 A: 账号密码 API 认证 ──


async def auth_via_api(username: str, password: str) -> httpx.AsyncClient | None:
    """通过 Riot Auth API 认证，返回带 session cookie 的客户端。"""
    print(cyan(f"\n📡 正在通过 Riot Auth API 认证 (用户: {username})..."))

    async with httpx.AsyncClient(
        timeout=30.0, follow_redirects=False,
        headers={"User-Agent": _USER_AGENT},
    ) as client:
        payload = {
            "type": "auth",
            "username": username,
            "password": password,
            "remember": True,
            "language": "en_US",
        }

        try:
            resp = await client.put(_AUTH_URL, json=payload)
        except httpx.RequestError as e:
            print(red(f"✗ 网络错误: {e}"))
            return None

        if resp.status_code != 200:
            print(red(f"✗ Auth API HTTP {resp.status_code}"))
            return None

        try:
            data = resp.json()
        except Exception:
            print(red("✗ Auth 响应 JSON 解析失败"))
            return None

        auth_type = data.get("type", "")

        if auth_type == "response":
            print(green("✓ Riot SSO 认证成功！"))
            return client

        if auth_type == "multifactor":
            print(yellow("⚠ Riot 账号需要二次验证（2FA/邮箱验证码）"))
            print(yellow("  API 方式不可用，请改用 Cookie 方式。"))
            return None

        if auth_type == "auth":
            error = data.get("error", "未知错误")
            if "captcha" in error.lower():
                print(yellow("⚠ Riot 登录需要 CAPTCHA 验证"))
                print(yellow("  API 方式不可用，请改用 Cookie 方式。"))
            elif "rate" in error.lower():
                print(yellow("⚠ 登录频率限制，请稍后再试。"))
            else:
                print(red(f"✗ 认证失败: {error}"))
            return None

        print(red(f"✗ 未知响应类型: {auth_type}"))
        return None


# ── 策略 B: Cookie 认证 ──


def create_cookie_client(cookies: dict[str, str]) -> httpx.AsyncClient:
    """用 Cookie 创建已认证的 HTTP 客户端。"""
    return httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=True,
        headers={"User-Agent": _USER_AGENT},
        cookies=cookies,
    )


# ── 从开发者门户获取 Key ──


async def fetch_key_from_portal(client: httpx.AsyncClient) -> str | None:
    """从 developer.riotgames.com 获取 API Key。"""
    print(cyan("🔍 正在从开发者门户获取 API Key..."))

    # 确保 session 已建立
    try:
        await client.get(_DEV_PORTAL)
    except Exception:
        pass

    # Step 1: GET 现有 Key
    try:
        resp = await client.get(_DEV_KEY_API)
        if resp.status_code == 200:
            data = resp.json()
            key = data.get("apiKey", data.get("key", ""))
            if key:
                print(green(f"✓ 获取现有 Key: ...{key[-6:]}"))
                return key
        elif resp.status_code == 401:
            print(red("✗ Cookie 已过期 (401 Unauthorized)"))
            return None
    except Exception as e:
        print(yellow(f"  GET key 异常: {e}"))

    # Step 2: PUT 重新生成 Key
    print(cyan("  Key 不存在，正在生成新 Key..."))
    try:
        resp = await client.put(_DEV_KEY_API)
        if resp.status_code == 200:
            data = resp.json()
            key = data.get("apiKey", data.get("key", ""))
            if key:
                print(green(f"✓ 生成新 Key: ...{key[-6:]}"))
                return key
        print(red(f"✗ PUT key HTTP {resp.status_code}: {resp.text[:200]}"))
    except Exception as e:
        print(red(f"  PUT key 异常: {e}"))

    # Step 3: 从页面直接提取（兜底）
    print(cyan("  尝试从页面提取 Key..."))
    try:
        resp = await client.get(f"{_DEV_PORTAL}/dashboard")
        if resp.status_code == 200:
            match = re.search(
                r'RGAPI-[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}',
                resp.text,
            )
            if match:
                key = match.group(0)
                print(green(f"✓ 从页面提取 Key: ...{key[-6:]}"))
                return key
    except Exception as e:
        print(yellow(f"  页面提取异常: {e}"))

    return None


# ── 验证 Key ──


async def validate_key(key: str) -> bool:
    """验证 API Key 是否有效。"""
    print(cyan(f"🔍 验证 Key: ...{key[-6:] if len(key) > 6 else key}"))
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                _VALIDATE_URL,
                params={"hl": "en-US"},
                headers={"User-Agent": _USER_AGENT, "x-api-key": key},
            )
            if resp.status_code == 200:
                print(green("✓ Key 有效！"))
                return True
            elif resp.status_code == 403:
                print(red("✗ Key 无效或已过期 (403)"))
            elif resp.status_code == 429:
                print(yellow("⚠ 请求频率限制 (429)，稍后重试"))
                return True
            else:
                print(yellow(f"⚠ 未知状态码: {resp.status_code}"))
    except Exception as e:
        print(yellow(f"⚠ 验证请求异常: {e}"))
        return True  # 网络异常保守认为有效
    return False


# ── 保存 Key ──


def save_key(key: str, output_path: str) -> None:
    """保存 API Key 到文件。"""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"key": key, "obtained_at": time.time()}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(green(f"\n✓ Key 已保存到: {path.absolute()}"))


# ── 打印 Cookie 获取指南 ──


def print_cookie_guide() -> None:
    print(f"""
{bold('📖 如何获取 Riot 开发者门户 Cookie:')}

  {bold('Chrome / Edge:')}
    1. 打开 https://developer.riotgames.com/ 并登录
    2. 按 F12 打开开发者工具
    3. 切换到 Application (应用程序) 标签
    4. 左侧 Storage → Cookies → developer.riotgames.com
    5. 你会看到一列 Name / Value 对

  {bold('需要哪些 Cookie？')}
    至少需要以下之一（越多越好）:
      • id_token       (Riot SSO 身份 token)
      • access_token   (访问 token)
      • 也可以直接把 developer.riotgames.com 下所有 cookie 都复制

  {bold('导出方式 A: 控制台一键导出')}
    在开发者工具 Console 中粘贴以下代码并回车:
    {cyan('copy(JSON.stringify(document.cookie.split("; ").reduce((o,c)=>{{const [k,v]=c.split("=");o[k]=v;return o}},{{}})))')}
    然后粘贴到文件 cookies.json 中，运行:
    {cyan('python refresh_riot_key.py --cookies-file cookies.json')}

  {bold('导出方式 B: 手动')}
    创建 cookies.json 文件，格式如下:
    {cyan('{{"id_token": "eyJ...", "access_token": "eyJ...", ...}}')}
""")


# ═══════════════════════════════════════════════
#  交互模式
# ═══════════════════════════════════════════════


def interactive_mode() -> argparse.Namespace:
    """交互式引导用户选择刷新方式。"""
    print(f"\n{bold('🎮 Riot API Key 刷新工具')}")
    print("=" * 50)

    print("\n请选择刷新方式:")
    print(f"  1. {bold('Cookie 方式')}（推荐，最稳定）")
    print(f"     - 需要从浏览器复制 Cookie")
    print(f"  2. {bold('账号密码方式')}")
    print(f"     - 直接用 Riot 账号密码登录")
    print(f"     - ⚠ 可能因 CAPTCHA/2FA 失败")

    while True:
        choice = input(f"\n{bold('请输入 1 或 2: ')}").strip()
        if choice in ("1", "2"):
            break

    args = argparse.Namespace()
    args.username = None
    args.password = None
    args.cookies_file = None
    args.cookies_json = None
    args.output = "data/riot_api_key.json"
    args.validate_only = False
    args.key = None
    args.interactive = True

    if choice == "1":
        print_cookie_guide()
        print(f"\n{bold('请粘贴 Cookie JSON:')}")
        print("  (可以是一行 JSON 对象，也可以是多行，输入空行结束)")
        lines = []
        while True:
            line = input()
            if not line.strip():
                if lines:
                    break
                continue
            lines.append(line)
        args.cookies_json = "\n".join(lines)

        # 也支持文件路径
        alt = input(f"\n{bold('或者输入 Cookie 文件路径 (直接回车跳过): ')}").strip()
        if alt and Path(alt).exists():
            args.cookies_file = alt
            args.cookies_json = None

    elif choice == "2":
        args.username = input(f"{bold('Riot 用户名: ')}").strip()
        args.password = input(f"{bold('Riot 密码: ')}").strip()
        if not args.username or not args.password:
            print(red("✗ 用户名和密码不能为空"))
            sys.exit(1)

    return args


# ═══════════════════════════════════════════════
#  主流程
# ═══════════════════════════════════════════════


async def main() -> None:
    args = parse_args()

    # 交互模式
    if args.interactive:
        args = interactive_mode()

    # 仅验证模式
    if args.validate_only:
        key = args.key or os.environ.get("RIOT_API_KEY", "")
        if not key:
            # 尝试从缓存读取
            cache_path = Path(args.output)
            if cache_path.exists():
                cached = json.loads(cache_path.read_text(encoding="utf-8"))
                key = cached.get("key", "")
        if not key:
            print(red("✗ 未提供 Key。请使用 --key 参数 或 设置 RIOT_API_KEY 环境变量。"))
            sys.exit(1)
        ok = await validate_key(key)
        print(green("✓ Key 有效！") if ok else red("✗ Key 无效！"))
        sys.exit(0 if ok else 1)

    key: str | None = None

    # ── 策略 1: Cookie 认证（最高成功率） ──
    cookies = load_cookies(args.cookies_file, args.cookies_json)
    if cookies:
        print(cyan(f"\n📡 策略 1: 用 Cookie 认证 (已加载 {len(cookies)} 个 Cookie)..."))
        client = create_cookie_client(cookies)
        try:
            key = await fetch_key_from_portal(client)
        finally:
            await client.aclose()

    # ── 策略 2: 账号密码 API 认证（兜底） ──
    if not key and args.username and args.password:
        print(cyan(f"\n📡 策略 2: 用账号密码认证..."))
        client = await auth_via_api(args.username, args.password)
        if client:
            try:
                key = await fetch_key_from_portal(client)
            finally:
                await client.aclose()

    # ── 无可用认证方式 ──
    if not key:
        print(red("\n✗ 无法自动获取 API Key。"))
        print()
        print_cookie_guide()
        print(yellow("\n请使用 Cookie 方式重试:"))
        print(cyan("  python refresh_riot_key.py --interactive"))
        sys.exit(1)

    # ── 验证 ──
    valid = await validate_key(key)
    if not valid:
        print(red("\n✗ Key 验证失败，可能无法正常使用。"))
        sys.exit(1)

    # ── 保存 ──
    save_key(key, args.output)

    print(f"""
{bold('🎉 完成！')}

插件将自动从以下位置加载 Key:
  1. 本地缓存: {Path(args.output).absolute()}
  2. 环境变量: RIOT_API_KEY

在 AstrBot 中使用 /lol apikey 查看 Key 状态。
""")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
