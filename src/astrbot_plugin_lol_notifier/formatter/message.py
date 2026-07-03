"""Text formatter for LoL notifications."""

from __future__ import annotations

from typing import Any

from ..models import LeagueMatch, LiveGameFrame, LiveMatch, MatchDetail, MatchGame, StandingEntry
from ..utils import replace_side_mentions


def format_schedule(matches: list[LeagueMatch], limit: int = 5) -> str:
    if not matches:
        return "📅 暂无比赛安排。"
    # 按日期距今天的绝对距离排序——最近的比赛优先
    from datetime import date, datetime
    today = date.today()
    def _proximity_key(m: LeagueMatch) -> tuple:
        try:
            d = datetime.strptime(m.start_date or "1970-01-01", "%Y-%m-%d").date()
            delta = abs((d - today).days)
            # 未来比赛优先于过去比赛（同天时）
            future_bonus = 0 if d >= today else 1
            return (delta, future_bonus)
        except ValueError:
            return (9999, 0)
    sorted_matches = sorted(matches, key=_proximity_key)
    lines = ["📅 LoL 近期赛程（最近优先）\n"]
    for match in sorted_matches[:limit]:
        teams = " vs ".join(match.teams) if match.teams else match.match_name or "未知对局"
        round_info = f"第{match.round}场 " if match.round else ""
        status_icon = {"completed": "✅", "finished": "✅", "live": "🔴", "in_progress": "🔴"}.get(
            match.status, "⏳"
        )
        lines.append(
            f"{status_icon} [{match.league.upper()} · {match.stage}] {round_info}{teams}\n"
            f"  时间: {match.start_date} {match.start_time}\n"
            f"  场馆: {match.arena or '未知'}"
        )
        # 已结束的比赛附加结果
        if match.status in ("completed", "finished") and match.games:
            winners = [g.winner for g in match.games if g.winner]
            if winners:
                score_parts = []
                for t in match.teams:
                    wins = winners.count(t)
                    score_parts.append(f"{t}({wins})")
                lines.append(f"  结果: {' vs '.join(score_parts)}")
        if match.status in ("live", "in_progress") and match.summary:
            lines.append(f"  比分: {match.summary}")
    return "\n".join(lines)


def _format_game(game: MatchGame) -> str:
    winner = f"，胜者: {game.winner}" if game.winner else ""
    return (
        f"Game {game.game_no}: {game.blue_team} vs {game.red_team}{winner}\n"
        f"  时长: {game.duration or '—'}"
    )


def format_match_result(match: LeagueMatch) -> str:
    if not match.games:
        return "⏳ 比赛结果暂未公布，请稍后再试。"
    lines = [
        f"🏆 比赛结果 — {match.league.upper()} {match.stage} 第{match.round}场",
        match.match_name or "",
        "",
    ]
    for game in match.games:
        lines.append(_format_game(game))
    return "\n".join(lines)


def format_match_bp(match: LeagueMatch | MatchDetail) -> str:
    if not match.games:
        return "⏳ BP 数据暂未公布，请稍后再试。"
    lines = [
        f"🧠 单局 BP — {match.league.upper()} {match.stage} 第{match.round}场",
        match.match_name or "",
        "",
    ]
    for game in match.games:
        lines.append(_format_game(game))
        for entry in getattr(game, "bp", []):
            lines.append(
                f"  {entry.side}: {entry.champion} - {entry.player} ({entry.result or '—'})"
            )
        lines.append("")
    return "\n".join(lines).rstrip()


def format_match_detail(detail: MatchDetail) -> str:
    if not detail.games:
        return "⏳ 比赛详细信息暂未公布，请稍后再试。"
    lines = [
        f"🧾 比赛详细信息 — {detail.league.upper()} {detail.stage} 第{detail.round}场",
        detail.match_name or "",
        detail.summary or "",
        "",
    ]
    for game in detail.games:
        lines.append(_format_game(game))
    return "\n".join(line for line in lines if line is not None).rstrip()


def format_match_basic(match: LeagueMatch) -> str:
    """格式化比赛基本信息（无对局详情时的回退）。"""
    if match is None:
        return "⏳ 比赛结果暂未公布，请稍后再试。"
    teams = " vs ".join(match.teams) if match.teams else match.match_name or "未知对局"
    status_icon = {"completed": "✅", "finished": "✅", "in_progress": "🔴", "unstarted": "⏳"}.get(match.status, "📅")
    lines = [
        f"{status_icon} 比赛结果 — {match.league.upper()} {match.stage}",
        teams,
        f"时间: {match.start_date} {match.start_time}",
    ]
    if match.arena:
        lines.append(f"场馆: {match.arena}")

    if match.games:
        winners = [g.winner for g in match.games if g.winner]
        if winners:
            score_parts = []
            for t in match.teams:
                wins = winners.count(t)
                score_parts.append(f"{t}({wins})")
            lines.append(f"结果: {' vs '.join(score_parts)}")

    if match.match_id:
        lines.append("\n💡 详细对局数据需要 Pandascore 高级套餐，当前套餐不可用。")
    return "\n".join(lines)


def format_standings(standings: list[StandingEntry]) -> str:
    if not standings:
        return "📊 暂无排名数据，请先接入赛事数据源。"
    lines = ["📊 排名 / 积分榜\n"]
    for entry in standings:
        lines.append(
            f"{entry.rank:>2}. {entry.team_name}  {entry.wins}胜-{entry.losses}负  {entry.points}分"
        )
    return "\n".join(lines)


def format_pre_match_preview(
    match: LeagueMatch,
    history: str | None = None,
    prediction: str | None = None,
    posters: str | None = None,
) -> str:
    lines = [
        f"⏳ 比赛前 30 分钟 — {match.league.upper()} {match.stage} 第{match.round}场",
        match.match_name or "",
        "",
        f"双方对阵: {' vs '.join(match.teams) if match.teams else '未知'}",
        f"开赛时间: {match.start_date} {match.start_time}",
    ]
    if posters:
        lines.append(f"海报链接: {posters}")
    if history:
        lines.append("\n历史交手:\n" + history)
    if prediction:
        lines.append("\n赛前预测:\n" + prediction)
    return "\n".join(lines).rstrip()


def format_post_match_summary(match: LeagueMatch, report: str | None = None, image_url: str | None = None) -> str:
    lines = [
        f"🎉 比赛战报 — {match.league.upper()} {match.stage} 第{match.round}场",
        match.match_name or "",
        "",
        format_match_result(match),
    ]
    if report:
        lines.append(f"\n赛后简述:\n{report}")
    if image_url:
        lines.append(f"图片: {image_url}")
    return replace_side_mentions("\n".join(lines), team_a=match.teams[0] if match.teams else "我方", team_b=match.teams[1] if len(match.teams) > 1 else "对方")


def format_bilibili_update(items: list[dict[str, Any]], account_name: str = "") -> str:
    """格式化 B 站视频更新推送消息

    items: [{"type":"video","bvid":"BV...","title":"...","pubdate":1234567890,"url":"...","cover":"..."}]
    account_name: B站 UP 主名称，如 "哔哩哔哩英雄联盟赛事"
    """
    if not items:
        return "📺 暂无 B 站账号更新。"

    name = account_name or "未知UP主"
    lines = [f"📣 UP 主「{name}」投稿了新视频：\n"]
    for i, item in enumerate(items, 1):
        title = item.get("title", "无标题")
        url = item.get("url", "")

        lines.append(f"标题: {title}")
        lines.append(f"链接: {url}")
        if len(items) > 1:
            lines.append("")

    return "\n".join(lines)


# ── BLG BP 图文动态 ──

def format_bilibili_bp_update(items: list[dict[str, Any]]) -> str:
    """格式化 BLG BP 图文动态推送消息。

    items: [{"dynamic_id":"...","text":"BP阵容...","images":[...],"url":"..."}]
    """
    if not items:
        return ""

    lines = [f"🔵 BLG 电子竞技俱乐部 · BP 更新\n"]
    for i, item in enumerate(items, 1):
        text = item.get("text", "")
        url = item.get("url", "")
        images = item.get("images", [])

        # 截断过长文本
        display_text = text[:200] + "..." if len(text) > 200 else text

        lines.append(f"━━ 第 {i} 条 ━━")
        lines.append(display_text)
        if url:
            lines.append(f"\n🔗 {url}")
        if images:
            lines.append(f"\n📷 图片 {len(images)} 张：")
            for j, img_url in enumerate(images[:4], 1):  # 最多显示 4 张
                lines.append(f"  [{j}] {img_url}")
        lines.append("")

    return "\n".join(lines)


# ── 微博赛前海报 ──

def format_weibo_poster(items: list[dict[str, Any]]) -> str:
    """格式化微博赛前海报推送消息。

    items: [{"id":"...","text":"...","images":[...],"url":"...","user_name":"..."}]
    """
    if not items:
        return ""

    lines = ["📢 LPL 赛前海报推送\n"]
    for i, item in enumerate(items, 1):
        user_name = item.get("user_name", "未知账号")
        text = item.get("text", "")
        url = item.get("url", "")
        images = item.get("images", [])

        display_text = text[:100] + "..." if len(text) > 100 else text

        lines.append(f"━━ {user_name} ━━")
        lines.append(display_text)
        if url:
            lines.append(f"\n🔗 {url}")
        if images:
            lines.append(f"\n🖼️ 海报 {len(images)} 张：")
            for j, img_url in enumerate(images[:3], 1):
                lines.append(f"  [{j}] {img_url}")
        lines.append("")

    return "\n".join(lines)


# ── 实时比赛格式化 ──

def format_live_game_frame(frame: LiveGameFrame) -> str:
    """格式化单局实时数据。"""
    lines = [
        f"第{frame.game_no}局 | {frame.state} | ⏱ {frame.game_time}",
        f"🔵 {frame.blue_team}: {frame.blue_kills}击杀 {frame.blue_gold}金 {frame.blue_towers}塔",
        f"🔴 {frame.red_team}: {frame.red_kills}击杀 {frame.red_gold}金 {frame.red_towers}塔",
    ]
    if frame.blue_barons or frame.red_barons:
        lines.append(f"  大龙: {frame.blue_barons} vs {frame.red_barons}")
    if frame.blue_drakes or frame.red_drakes:
        lines.append(f"  小龙: {frame.blue_drakes} vs {frame.red_drakes}")
    if frame.winner:
        lines.append(f"  🏆 胜方: {frame.winner}")
    return "\n".join(lines)

def format_live_match(live: LiveMatch) -> str:
    """格式化实时比赛为消息。"""
    lines = [
        f"📡 实时比分 — {live.league_name} {live.bo_type}",
        f"⚔️ {live.match_name}  ({live.score})",
        "",
    ]
    for game in live.games:
        lines.append(format_live_game_frame(game))
        lines.append("")

    if not live.games:
        lines.append("⏳ 等待比赛开始...")

    return "\n".join(lines).rstrip()


# ═══════════════════════════════════════════════════
#  每日赛程 & 赛前预告
# ═══════════════════════════════════════════════════

def _league_display_name(league_name: str) -> str:
    """将 Pandascore 原始联赛名映射为用户友好的中文/缩写名。"""
    mapping = {
        "lpl": "LPL",
        "lck": "LCK",
        "lec": "LEC",
        "lcs": "LCS",
        "worlds": "Worlds",
        "world championship": "Worlds",
        "mid-season invitational": "MSI",
        "msi": "MSI",
        "lco": "LCO",
        "vcs": "VCS",
        "pcs": "PCS",
        "lla": "LLA",
        "cblol": "CBLOL",
        "tcl": "TCL",
        "lcl": "LCL",
        "ljl": "LJL",
    }
    key = league_name.strip().lower()
    return mapping.get(key, league_name.upper())


def format_daily_schedule(matches: list[LeagueMatch]) -> str:
    """格式化每日赛程推送。

    Args:
        matches: 当天开始的比赛列表
    """
    if not matches:
        return "📅 今日无赛程，好好休息一下吧~"

    # 按联赛分组
    by_league: dict[str, list[LeagueMatch]] = {}
    for m in matches:
        league_key = _league_display_name(m.league)
        by_league.setdefault(league_key, []).append(m)

    lines = ["📅 今日赛程安排\n"]

    for league_name, league_matches in by_league.items():
        lines.append(f"━━━ {league_name} ━━━")
        for match in league_matches:
            teams = " vs ".join(match.teams) if match.teams else match.match_name or "未知对局"
            bo_info = f" ({match.bo_type})" if match.bo_type else ""
            status_icon = {"live": "🔴", "in_progress": "🔴", "completed": "✅"}.get(match.status, "⏳")
            lines.append(
                f"{status_icon} {teams}{bo_info}\n"
                f"   ⏰ {match.start_time}"
            )
        lines.append("")

    lines.append("祝大家观赛愉快！🎉")
    return "\n".join(lines)


def format_pre_match_alert(match: LeagueMatch) -> str:
    """格式化赛前 10 分钟预告。

    Args:
        match: 即将开始的比赛
    """
    teams = " vs ".join(match.teams) if match.teams else match.match_name or "未知对局"
    league_short = _league_display_name(match.league)
    bo_info = f" ({match.bo_type})" if match.bo_type else ""

    lines = [
        f"⚡ 比赛即将开始！",
        f"",
        f"🏆 {league_short} · {match.stage}",
        f"⚔️ {teams}{bo_info}",
        f"⏰ {match.start_time} 开赛",
    ]
    return "\n".join(lines)


# ═══════════════════════════════════════════════════
#  参考数据 — Champions / Items / Spells / Runes / Masteries
# ═══════════════════════════════════════════════════

def _extract_items(raw: Any) -> list[dict]:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        return raw.get("data", raw.get("items", raw.get("champions", []))) or []
    return []


def format_champions(raw: Any, limit: int = 15) -> str:
    items = _extract_items(raw)
    if not items:
        return "📋 暂无英雄数据。"
    lines = ["📋 **英雄列表**", ""]
    for c in items[:limit]:
        name = c.get("name", "?")
        armor = c.get("armor", "?")
        hp = c.get("hp", "?")
        image = c.get("image_url", "")
        lines.append(f"  {name}  🛡{armor}  ❤{hp}")
    if len(items) > limit:
        lines.append(f"  ... 还有 {len(items) - limit} 个")
    return "\n".join(lines)


def format_items(raw: Any, limit: int = 15) -> str:
    items = _extract_items(raw)
    if not items:
        return "📋 暂无装备数据。"
    lines = ["🎒 **装备列表**", ""]
    for it in items[:limit]:
        name = it.get("name", "?")
        gold = it.get("total_gold", it.get("gold", {}).get("total", "?"))
        lines.append(f"  {name}  💰{gold}")
    if len(items) > limit:
        lines.append(f"  ... 还有 {len(items) - limit} 件")
    return "\n".join(lines)


def format_spells(raw: Any) -> str:
    items = _extract_items(raw)
    if not items:
        return "📋 暂无召唤师技能数据。"
    lines = ["✨ **召唤师技能**", ""]
    for s in items:
        name = s.get("name", "?")
        cd = s.get("cooldown", "?")
        lines.append(f"  {name}  ⏱冷却 {cd}s")
    return "\n".join(lines)


def format_runes(raw: Any, limit: int = 20) -> str:
    """格式化符文（runes-reforged 格式）。"""
    items = _extract_items(raw)
    if not items:
        return "📋 暂无符文数据。"
    lines = ["🔮 **符文**", ""]
    for r in items[:limit]:
        name = r.get("name", "?")
        path = r.get("rune_path_name", r.get("rune_path", {}).get("name", "")) if isinstance(r, dict) else ""
        line = f"  {name}"
        if path:
            line += f"  [{path}]"
        lines.append(line)
    if len(items) > limit:
        lines.append(f"  ... 还有 {len(items) - limit} 个")
    return "\n".join(lines)


def format_rune_paths(raw: Any) -> str:
    items = _extract_items(raw)
    if not items:
        return "📋 暂无符文系数据。"
    lines = ["📂 **符文系**", ""]
    for p in items:
        name = p.get("name", "?")
        runes = p.get("runes", [])
        count = len(runes) if isinstance(runes, list) else 0
        lines.append(f"  {name}  ({count} 个符文)")
    return "\n".join(lines)


def format_masteries(raw: Any) -> str:
    items = _extract_items(raw)
    if not items:
        return "📋 暂无天赋数据。"
    lines = ["🎯 **天赋**", ""]
    for m in items[:15]:
        name = m.get("name", "?")
        lines.append(f"  {name}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════
#  对局扩展 — Events / Frames / Match Games
# ═══════════════════════════════════════════════════

def format_game_events(raw: Any, limit: int = 50) -> str:
    events = raw if isinstance(raw, list) else raw.get("data", raw.get("events", [])) if isinstance(raw, dict) else []
    if not events:
        return "📋 暂无事伴数据。"
    lines = ["📡 **对局事伴**", ""]
    for e in events[:limit]:
        etype = e.get("type", "?")
        ts = e.get("timestamp", e.get("game_timestamp", ""))
        team = e.get("team", {}).get("name", "") if isinstance(e.get("team"), dict) else ""
        line = f"  [{ts}] {etype}"
        if team:
            line += f"  ({team})"
        lines.append(line)
    if len(events) > limit:
        lines.append(f"  ... 还有 {len(events) - limit} 个")
    return "\n".join(lines)


def format_game_frames(raw: Any, limit: int = 20) -> str:
    frames = raw if isinstance(raw, list) else raw.get("data", raw.get("frames", [])) if isinstance(raw, dict) else []
    if not frames:
        return "📋 暂无帧数据。"
    lines = ["🎞 **对局帧**", ""]
    for f in frames[:limit]:
        num = f.get("frame_number", f.get("num", "?"))
        blue_gold = f.get("blue_team", {}).get("total_gold", "?") if isinstance(f.get("blue_team"), dict) else "?"
        red_gold = f.get("red_team", {}).get("total_gold", "?") if isinstance(f.get("red_team"), dict) else "?"
        lines.append(f"  帧 {num}: 🔵{blue_gold}g  🔴{red_gold}g")
    return "\n".join(lines)


def format_match_games(raw: Any) -> str:
    games = raw if isinstance(raw, list) else raw.get("data", raw.get("games", [])) if isinstance(raw, dict) else []
    if not games:
        return "📋 暂无对局数据。"
    lines = ["🎮 **比赛对局**", ""]
    for g in games:
        pos = g.get("position", "?")
        winner = g.get("winner", {}).get("name", "TBD") if isinstance(g.get("winner"), dict) else "TBD"
        length = g.get("length", 0) or 0
        dur = f"{length // 60}:{length % 60:02d}" if length else ""
        lines.append(f"  Game {pos}: 🏆{winner}  ⏱{dur}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════
#  选手 & 战队
# ═══════════════════════════════════════════════════

def format_players(raw: Any, limit: int = 15) -> str:
    items = _extract_items(raw)
    if not items:
        return "📋 暂无选手数据。"
    lines = ["👤 **选手列表**", ""]
    for p in items[:limit]:
        name = p.get("name", "?")
        role = p.get("role", p.get("position", "?"))
        team = p.get("current_team", {}).get("name", "") if isinstance(p.get("current_team"), dict) else ""
        line = f"  {name}  ({role})"
        if team:
            line += f"  — {team}"
        lines.append(line)
    if len(items) > limit:
        lines.append(f"  ... 还有 {len(items) - limit} 位")
    return "\n".join(lines)


def format_player(raw: Any) -> str:
    if not isinstance(raw, dict):
        return "📋 选手数据格式错误。"
    data = raw.get("data", raw)
    name = data.get("name", "?")
    role = data.get("role", "?")
    hometown = data.get("hometown", "")
    team = data.get("current_team", {})
    team_name = team.get("name", "") if isinstance(team, dict) else ""
    lines = [f"👤 **{name}**"]
    if team_name:
        lines.append(f"  战队: {team_name}")
    lines.append(f"  位置: {role}")
    if hometown:
        lines.append(f"  国籍: {hometown}")
    return "\n".join(lines)


def format_player_stats(raw: Any) -> str:
    if not isinstance(raw, dict):
        return "📋 统计数据格式错误。"
    data = raw.get("data", raw)
    player = data.get("player", {}) if isinstance(data.get("player"), dict) else {}
    name = player.get("name", "?")
    lines = [f"📊 **{name}** 统计数据", ""]
    # 遍历统计字段
    for key, val in data.items():
        if key in ("player", "team"):
            continue
        if isinstance(val, (int, float)):
            lines.append(f"  {key}: {val}")
    return "\n".join(lines) if len(lines) > 1 else f"📊 {name}: 暂无详细统计"


# ═══════════════════════════════════════════════════
#  系列赛 & 锦标赛
# ═══════════════════════════════════════════════════

def format_series(raw: Any, limit: int = 10) -> str:
    items = _extract_items(raw)
    if not items:
        return "📋 暂无系列赛数据。"
    lines = ["🏆 **系列赛列表**", ""]
    for s in items[:limit]:
        name = s.get("name", s.get("full_name", "?"))
        season = s.get("season", "")
        begin = s.get("begin_at", "")[:10]
        end = s.get("end_at", "")[:10]
        line = f"  {name}"
        if begin and end:
            line += f"  ({begin} ~ {end})"
        lines.append(line)
    return "\n".join(lines)


def format_series_detail(raw: Any) -> str:
    if not isinstance(raw, dict):
        return "📋 系列赛数据格式错误。"
    data = raw.get("data", raw)
    name = data.get("name", data.get("full_name", "?"))
    season = data.get("season", "")
    begin = data.get("begin_at", "")[:10]
    end = data.get("end_at", "")[:10]
    league = data.get("league", {}).get("name", "") if isinstance(data.get("league"), dict) else ""
    return (
        f"🏆 **{name}**\n"
        f"  联赛: {league or '—'}\n"
        f"  赛季: {season}\n"
        f"  时间: {begin} ~ {end}"
    )


def format_tournaments(raw: Any, limit: int = 10) -> str:
    items = _extract_items(raw)
    if not items:
        return "📋 暂无锦标赛数据。"
    lines = ["🏅 **锦标赛列表**", ""]
    for t in items[:limit]:
        name = t.get("name", "?")
        begin = t.get("begin_at", "")[:10]
        end = t.get("end_at", "")[:10]
        league = t.get("league", {}).get("name", "") if isinstance(t.get("league"), dict) else ""
        line = f"  {name}  ({begin} ~ {end})"
        if league:
            line += f"  [{league}]"
        lines.append(line)
    return "\n".join(lines)


def format_tournament(raw: Any) -> str:
    if not isinstance(raw, dict):
        return "📋 锦标赛数据格式错误。"
    data = raw.get("data", raw)
    name = data.get("name", "?")
    begin = data.get("begin_at", "")[:10]
    end = data.get("end_at", "")[:10]
    league = data.get("league", {}).get("name", "") if isinstance(data.get("league"), dict) else ""
    prize = data.get("prizepool", "")
    return (
        f"🏅 **{name}**\n"
        f"  联赛: {league or '—'}\n"
        f"  时间: {begin} ~ {end}\n"
        f"  奖金池: {prize or '—'}"
    )


def format_match_players_stats(raw: Any, limit: int = 15) -> str:
    """格式化比赛选手统计。"""
    items = raw if isinstance(raw, list) else raw.get("data", []) if isinstance(raw, dict) else []
    if not items:
        return "📋 暂无选手统计数据。"
    lines = ["📊 **比赛选手统计**", ""]
    for p in items[:limit]:
        player = p.get("player", {}) if isinstance(p.get("player"), dict) else {}
        name = player.get("name", "?")
        kills = p.get("kills", "—")
        deaths = p.get("deaths", "—")
        assists = p.get("assists", "—")
        champ = p.get("champion", {}).get("name", "") if isinstance(p.get("champion"), dict) else ""
        line = f"  {name}  {kills}/{deaths}/{assists}"
        if champ:
            line += f"  ({champ})"
        lines.append(line)
    return "\n".join(lines)


def format_team_stats(raw: Any) -> str:
    if not isinstance(raw, dict):
        return "📋 战队统计数据格式错误。"
    data = raw.get("data", raw)
    team = data.get("team", {}) if isinstance(data.get("team"), dict) else {}
    name = team.get("name", "?")
    lines = [f"📊 **{name}** 统计数据", ""]
    for key, val in data.items():
        if key in ("team",):
            continue
        if isinstance(val, (int, float)):
            lines.append(f"  {key}: {val}")
    if len(lines) == 2:
        lines.append("  (详细统计待补充)")
    return "\n".join(lines)


def format_tournament_teams_stats(raw: Any, limit: int = 15) -> str:
    items = raw if isinstance(raw, list) else raw.get("data", []) if isinstance(raw, dict) else []
    if not items:
        return "📋 暂无战队统计数据。"
    lines = ["📊 **锦标赛战队统计**", ""]
    for t in items[:limit]:
        team = t.get("team", {}) if isinstance(t.get("team"), dict) else {}
        name = team.get("name", "?")
        wins = t.get("wins", "—")
        losses = t.get("losses", "—")
        lines.append(f"  {name}  ✅{wins} ❌{losses}")
    return "\n".join(lines)


def format_team_info(data: dict) -> str:
    """格式化战队信息。支持单队 dict 或 {"teams": [...]} 批量格式。"""
    # 批量格式：{"teams": [...]}
    teams_list = data.get("teams")
    if teams_list and isinstance(teams_list, list):
        if not teams_list:
            return "🏢 暂无战队数据。"
        lines = [f"🏢 共 {len(teams_list)} 支战队：\n"]
        for t in teams_list:
            if not isinstance(t, dict):
                continue
            name = t.get("name") or t.get("acronym") or "?"
            region = t.get("location", t.get("home_league", {}).get("name", "")) if isinstance(
                t.get("home_league"), dict
            ) else t.get("location", "")
            acronym = t.get("acronym", "")
            slug = t.get("slug", "")
            lines.append(f"  • {name}" + (f" ({acronym})" if acronym else ""))
            if region:
                lines.append(f"    赛区: {region}")
            if slug:
                lines.append(f"    标识: {slug}")
        return "\n".join(lines)

    # 单队格式
    name = data.get("name", data.get("code", data.get("acronym", "未知战队")))
    region = data.get("location", data.get("region", data.get("league", "")))
    if isinstance(region, dict):
        region = region.get("name", "")
    slug = data.get("slug", "")
    acronym = data.get("acronym", "")
    image = data.get("image", data.get("logoUrl", ""))
    lines = [f"🏢 {name}"]
    if acronym:
        lines.append(f"缩写: {acronym}")
    if region:
        lines.append(f"赛区: {region}")
    if slug:
        lines.append(f"标识: {slug}")
    if image:
        lines.append(f"队标: {image}")
    return "\n".join(lines)


def format_game_info(data: dict) -> str:
    """格式化单局详情 GET /lol/games/{id} 的原始返回。"""
    import json
    game_id = data.get("id", "")
    position = data.get("position", "")
    status = data.get("status", "")
    length = data.get("length", 0) or 0
    duration = f"{length // 60}:{length % 60:02d}" if length > 0 else "N/A"

    winner = data.get("winner", {}) or {}
    winner_name = winner.get("name", "N/A") if isinstance(winner, dict) else str(winner)

    match_data = data.get("match", {}) or {}
    match_name = match_data.get("name", "")

    teams = data.get("teams", []) or []
    team_lines = []
    for t in teams:
        if isinstance(t, dict):
            t_name = t.get("name", "")
            t_side = t.get("side", "")
            side_tag = f"[{t_side}]" if t_side else ""
            team_lines.append(f"  {side_tag} {t_name}")

    lines = [
        f"🎮 对局详情",
        f"Game ID: {game_id}",
    ]
    if match_name:
        lines.append(f"所属比赛: {match_name}")
    lines.append(f"局数: #{position}")
    lines.append(f"状态: {status}")
    lines.append(f"时长: {duration}")
    lines.append(f"胜者: {winner_name}")
    if team_lines:
        lines.append("队伍:")
        lines.extend(team_lines)
    return "\n".join(lines)


