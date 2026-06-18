"""LoL Esports 官方数据抓取器。

数据来源：lolesports.com 公开 API（无需 API Key）。
- 赛程 / 排名: esports-api.lolesports.com/persisted/gw
- 实时比赛帧数据: feed.lolesports.com/livestats/v1/window
- 比赛详情: esports-api.lolesports.com/persisted/gw/getEventDetails

League ID 参考：
  LCK: 98767991302996019
  LPL: 98767991314006698
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import httpx

from astrbot.api import logger
from ..models import (
    BPEntry,
    Failure,
    LeagueMatch,
    LiveGameFrame,
    LiveMatch,
    LiveResult,
    MatchDetail,
    MatchGame,
    ScheduleResult,
    StandingEntry,
    StandingsResult,
    Success,
)

# ── 常量 ──

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

_BASE_SCHEDULE = "https://esports-api.lolesports.com/persisted/gw"
_BASE_FEED = "https://feed.lolesports.com/livestats/v1"

# LoL Esports API key — 来自 lolesports.com 网页端，公开可用
_LOL_API_KEY = "0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z"

# League ID 映射
_LEAGUE_IDS: dict[str, str] = {
    "lck": "98767991302996019",
    "lpl": "98767991314006698",
}
_LEAGUE_NAMES: dict[str, str] = {"lck": "LCK", "lpl": "LPL"}

# 单例 httpx client（复用连接）
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=15.0,
            headers={
                "User-Agent": _USER_AGENT,
                "Accept": "application/json",
                "x-api-key": _LOL_API_KEY,
                "Origin": "https://lolesports.com",
                "Referer": "https://lolesports.com/",
            },
        )
    return _client


async def close_session() -> None:
    global _client
    if _client:
        await _client.aclose()
        _client = None


# ── API 请求工具 ──

async def _request(url: str, params: dict | None = None) -> dict[str, Any]:
    client = _get_client()
    try:
        resp = await client.get(url, params=params or {})
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", data)
    except httpx.HTTPStatusError as e:
        logger.debug(f"[LoLEsports] HTTP {e.response.status_code} for {url}")
        return {}
    except Exception as e:
        logger.debug(f"[LoLEsports] Request failed: {url} — {e}")
        return {}


# ═══════════════════════════════════════════════════
#  赛程
# ═══════════════════════════════════════════════════

async def fetch_schedule(league: str = "lck") -> ScheduleResult:
    """获取 League 近期赛程"""
    league_id = _LEAGUE_IDS.get(league)
    if not league_id:
        return Failure(error=f"不支持的赛区: {league}")

    data = await _request(
        f"{_BASE_SCHEDULE}/getSchedule",
        params={"hl": "zh-CN", "leagueId": league_id},
    )
    schedule_data = data.get("schedule", data)

    events = schedule_data.get("events", [])
    matches: list[LeagueMatch] = []

    for ev in events:
        if ev.get("type") != "match":
            continue
        match_obj = ev.get("match", {})
        teams_raw = match_obj.get("teams", [])
        teams = [t.get("name", t.get("code", "?")) for t in teams_raw]

        strategy = match_obj.get("strategy", {})
        start_time = ev.get("startTime", "")
        dt = _parse_iso(start_time) if start_time else ("", "")

        matches.append(LeagueMatch(
            league=league.upper(),
            stage=strategy.get("type", "regular"),
            round=str(match_obj.get("id", "")),
            match_name=" vs ".join(teams) if teams else "",
            bo_type=f"BO{strategy.get('count', 0)}",
            start_date=dt[0],
            start_time=dt[1],
            status=match_obj.get("state", ""),
            arena=ev.get("blockName", ev.get("league", {}).get("name", "")),
            teams=teams,
        ))

    return Success(value=matches) if matches else Success(value=[])


# ═══════════════════════════════════════════════════
#  实时比赛
# ═══════════════════════════════════════════════════

async def fetch_live_matches(league: str | None = None) -> LiveResult:
    """获取正在进行的比赛（可选筛选赛区）"""
    data = await _request(
        f"{_BASE_SCHEDULE}/getLive",
        params={"hl": "zh-CN"},
    )
    schedule = data.get("schedule", data)
    events = schedule.get("events", [])
    live_matches: list[LiveMatch] = []

    for ev in events:
        if ev.get("type") != "match":
            continue
        match_obj = ev.get("match", {})
        tournament = ev.get("tournament", {})
        league_id = tournament.get("leagueId", "")

        # 赛区筛选
        if league and league not in _LEAGUE_IDS:
            continue
        if league and league_id != _LEAGUE_IDS.get(league):
            continue

        league_name = _league_name_by_id(league_id)

        teams_raw = match_obj.get("teams", [])
        teams = []
        for t in teams_raw:
            teams.append(t.get("name", t.get("code", "?")))

        strategy = match_obj.get("strategy", {})

        # 解析对局
        games = []
        for g in match_obj.get("games", []):
            game_id = g.get("id", "")
            state = g.get("state", "")
            teams_in_game = g.get("teams", [])
            blue = _pick_side(teams_in_game, "blue")
            red = _pick_side(teams_in_game, "red")

            games.append(LiveGameFrame(
                game_id=game_id,
                game_no=g.get("number", 0),
                state=state,
                blue_team=blue.get("name", blue.get("code", "蓝方")),
                red_team=red.get("name", red.get("code", "红方")),
                winner="blue" if blue.get("result", {}).get("outcome") == "win" else (
                    "red" if red.get("result", {}).get("outcome") == "win" else ""
                ),
            ))

        # 比分
        blue_wins = sum(1 for g in games if g.winner == "blue")
        red_wins = sum(1 for g in games if g.winner == "red")
        score = f"{blue_wins}:{red_wins}"

        live_matches.append(LiveMatch(
            match_id=match_obj.get("id", ""),
            league=league_name.lower(),
            league_name=league_name,
            tournament_id=tournament.get("id", ""),
            match_name=" vs ".join(teams) if teams else "",
            teams=teams,
            score=score,
            bo_type=f"BO{strategy.get('count', 0)}",
            status=match_obj.get("state", ""),
            games=games,
        ))

    return Success(value=live_matches)


# ═══════════════════════════════════════════════════
#  实时比赛帧数据（击杀/经济/防御塔/龙/男爵）
# ═══════════════════════════════════════════════════

async def fetch_live_frame(game_id: str, since: int = 0) -> LiveGameFrame | None:
    """获取某一局比赛的实时帧数据。since=0 获取最新帧。

    返回 LiveGameFrame 包含击杀/经济/塔/龙/男爵/水晶等实时数据。
    """
    url = f"{_BASE_FEED}/window/{game_id}"
    params: dict = {"hl": "zh-CN"}
    if since > 0:
        params["startingTime"] = str(since)

    try:
        data = await _request(url, params)
        # feed API 直接返回 frames 数组
        frames = data.get("frames", []) if isinstance(data, dict) else []

        if not frames:
            # Try: data itself might be a list of frames
            if isinstance(data, list):
                frames = data[-1:]  # take latest
            else:
                return None

        latest = frames[-1] if frames else {}
        game_state = latest.get("gameState", data.get("gameState", ""))

        blue = latest.get("blueTeam", {})
        red = latest.get("redTeam", {})

        return LiveGameFrame(
            game_id=game_id,
            game_no=0,
            state=game_state,
            blue_team=blue.get("name", ""),
            red_team=red.get("name", ""),
            blue_kills=blue.get("totalKills", 0),
            red_kills=red.get("totalKills", 0),
            blue_gold=blue.get("totalGold", 0),
            red_gold=red.get("totalGold", 0),
            blue_towers=blue.get("towers", 0),
            red_towers=red.get("towers", 0),
            blue_barons=blue.get("barons", 0),
            red_barons=red.get("barons", 0),
            blue_drakes=blue.get("drakes", 0),
            red_drakes=red.get("drakes", 0),
            blue_inhibitors=blue.get("inhibitors", 0),
            red_inhibitors=red.get("inhibitors", 0),
            game_time=latest.get("gameTime", ""),
            winner=data.get("winner", ""),
        )
    except Exception as e:
        logger.debug(f"[LoLEsports] Frame fetch error for {game_id}: {e}")
        return None


async def fetch_live_match_details(live_match: LiveMatch) -> LiveMatch:
    """为 LiveMatch 的每局填充实时帧数据"""
    updated_games: list[LiveGameFrame] = []
    for game in live_match.games:
        if game.state == "in_progress" and game.game_id:
            frame = await fetch_live_frame(game.game_id)
            if frame:
                frame.game_no = game.game_no
                updated_games.append(frame)
            else:
                updated_games.append(game)
        else:
            updated_games.append(game)
    live_match.games = updated_games
    return live_match


# ═══════════════════════════════════════════════════
#  排名
# ═══════════════════════════════════════════════════

async def fetch_standings(league: str = "lck") -> StandingsResult:
    """获取 League 排名/积分榜"""
    league_id = _LEAGUE_IDS.get(league)
    if not league_id:
        return Failure(error=f"不支持的赛区: {league}")

    data = await _request(
        f"{_BASE_SCHEDULE}/getStandings",
        params={"hl": "zh-CN", "tournamentId": league_id},
    )

    standings_list = data.get("standings", [])
    entries: list[StandingEntry] = []

    for standing_group in standings_list:
        for team in standing_group.get("teams", []):
            entries.append(StandingEntry(
                rank=team.get("rank", 0),
                team_name=team.get("name", team.get("code", "?")),
                wins=team.get("record", {}).get("wins", 0),
                losses=team.get("record", {}).get("losses", 0),
                points=team.get("record", {}).get("wins", 0),
                status=team.get("status", ""),
            ))

    return Success(value=entries)


# ═══════════════════════════════════════════════════
#  比赛详情 (含 BP)
# ═══════════════════════════════════════════════════

async def fetch_match_detail(match_id: str) -> MatchDetail | None:
    """获取某场比赛详细信息（含 BP 阵容）"""
    data = await _request(
        f"{_BASE_SCHEDULE}/getEventDetails",
        params={"hl": "zh-CN", "eventId": match_id},
    )
    event = data.get("event", data)
    if not event:
        return None

    match_obj = event.get("match", {})
    teams_raw = match_obj.get("teams", [])
    teams = [t.get("name", t.get("code", "?")) for t in teams_raw]

    games: list[MatchGame] = []
    for g in match_obj.get("games", []):
        game_teams = g.get("teams", [])
        blue = _pick_side(game_teams, "blue")
        red = _pick_side(game_teams, "red")

        bp_entries: list[BPEntry] = []
        # 解析 bans/picks
        for side_name, side_data in [("蓝方", blue), ("红方", red)]:
            for ban in side_data.get("bans", []):
                bp_entries.append(BPEntry(
                    side=side_name,
                    champion=ban.get("name", ban.get("championId", "")),
                    player="(ban)",
                    result="ban",
                ))
            for pick in side_data.get("picks", []):
                bp_entries.append(BPEntry(
                    side=side_name,
                    champion=pick.get("name", pick.get("championId", "")),
                    player=pick.get("playerId", pick.get("player", "")),
                    result=pick.get("role", ""),
                ))

        winner = "blue" if blue.get("result", {}).get("outcome") == "win" else (
            "red" if red.get("result", {}).get("outcome") == "win" else ""
        )
        winner_name = blue.get("name", "") if winner == "blue" else (
            red.get("name", "") if winner == "red" else ""
        )

        games.append(MatchGame(
            game_no=g.get("number", 0),
            blue_team=blue.get("name", blue.get("code", "蓝方")),
            red_team=red.get("name", red.get("code", "红方")),
            winner=winner_name,
            duration=_format_duration(g.get("duration", 0)),
            bp=bp_entries,
        ))

    tournament = event.get("tournament", {})
    league_name = _league_name_by_id(tournament.get("leagueId", ""))

    return MatchDetail(
        league=league_name,
        stage=tournament.get("stage", "regular"),
        round=str(match_obj.get("id", "")),
        match_name=" vs ".join(teams) if teams else "",
        summary=event.get("description", ""),
        games=games,
    )


# ═══════════════════════════════════════════════════
#  工具函数
# ═══════════════════════════════════════════════════

def _league_name_by_id(league_id: str) -> str:
    for key, lid in _LEAGUE_IDS.items():
        if lid == league_id:
            return key.upper()
    return ""


def _parse_iso(iso_str: str) -> tuple[str, str]:
    """ISO 8601 → (date, time)"""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        local = dt.astimezone()
        return (local.strftime("%Y-%m-%d"), local.strftime("%H:%M"))
    except Exception:
        return ("", "")


def _pick_side(teams: list[dict], side: str) -> dict:
    """从 teams 列表取出 blue/red 侧"""
    for t in teams:
        if t.get("side", "").lower() == side:
            return t
    return {}


def _format_duration(seconds: int) -> str:
    if not seconds:
        return ""
    m, s = divmod(seconds, 60)
    return f"{m}:{s:02d}"
