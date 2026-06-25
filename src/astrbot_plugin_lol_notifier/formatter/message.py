"""Text formatter for LoL notifications."""

from __future__ import annotations

from typing import Any

from ..models import LeagueMatch, LiveGameFrame, LiveMatch, MatchDetail, MatchGame, StandingEntry
from ..utils import replace_side_mentions


def format_schedule(matches: list[LeagueMatch], limit: int = 5) -> str:
    if not matches:
        return "📅 暂无可用赛程数据，请先接入赛事数据源。"
    lines = ["📅 LoL 近期赛程\n"]
    for match in matches[:limit]:
        teams = " vs ".join(match.teams) if match.teams else match.match_name or "未知对局"
        lines.append(
            f"[{match.league.upper()} · {match.stage}] 第{match.round}场 {teams}\n"
            f"  时间: {match.start_date} {match.start_time}\n"
            f"  场馆: {match.arena or '未知'}"
        )
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


def format_match_bp(match: LeagueMatch) -> str:
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


def format_standings(standings: list[StandingEntry]) -> str:
    if not standings:
        return "📊 暂无排名数据，请先接入赛事数据源。"
    lines = ["📊 排名 / 积分榜\n"]
    for entry in standings:
        lines.append(
            f"{entry.rank:>2}. {entry.team_name}  {entry.wins}胜-{entry.losses}负  {entry.points}分"
        )
    return "\n".join(lines)


def format_lineup_message(lineup: dict[str, Any], team_a: str, team_b: str) -> str:
    entries = lineup.get("lineup", [])
    if not entries:
        return "📋 暂无首发名单数据。"
    lines = [f"📋 {team_a} vs {team_b} 首发名单"]
    for item in entries:
        side = item.get("side", "")
        lines.append(
            f"  {side} | {item.get('player', '')} - {item.get('champion', '')}"
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


def format_elimination_update(bracket_info: dict[str, Any]) -> str:
    if not bracket_info:
        return "⚠️ 暂无淘汰赛关键节点数据。"
    lines = [
        "🏆 淘汰赛关键节点更新",
        f"当前阶段: {bracket_info.get('round', '')}",
        f"状态: {bracket_info.get('status', '')}",
    ]
    if bracket_info.get("winner"):
        lines.append(f"晋级: {bracket_info.get('winner')}")
    if next_match := bracket_info.get("next_match"):
        lines.append(f"后续对阵: {next_match}")
    return "\n".join(lines)


def format_bilibili_update(items: list[dict[str, Any]]) -> str:
    """格式化 B 站视频更新推送消息

    items: [{"type":"video","bvid":"BV...","title":"...","pubdate":1234567890,"url":"...","cover":"..."}]
    """
    if not items:
        return "📺 暂无 B 站官号更新。"

    lines = [f"📺 B 站官号更新了 {len(items)} 个视频：\n"]
    for i, item in enumerate(items, 1):
        title = item.get("title", "无标题")
        url = item.get("url", "")
        bvid = item.get("bvid", "")
        desc = item.get("description", "")
        summary = f"{desc[:60]}..." if len(desc) > 60 else desc

        lines.append(f"{i}. {title}")
        lines.append(f"   BV: {bvid}")
        if summary:
            lines.append(f"   {summary}")
        lines.append(f"   {url}")
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
    """格式化单局实时帧数据为紧凑状态条。"""
    bar_len = 20

    # 击杀进度条
    total_k = frame.blue_kills + frame.red_kills
    if total_k > 0:
        blue_fill = int(bar_len * frame.blue_kills / max(total_k, 1))
        red_fill = bar_len - blue_fill
        bar = "█" * blue_fill + "░" * red_fill
    else:
        bar = "░" * bar_len

    # 经济差
    gold_diff = frame.blue_gold - frame.red_gold
    if gold_diff > 0:
        gold_str = f" 🔵 +{gold_diff // 1000}k"
    elif gold_diff < 0:
        gold_str = f" 🔴 +{abs(gold_diff) // 1000}k"
    else:
        gold_str = ""

    status_icon = {"in_progress": "▶️", "paused": "⏸️", "finished": "🏁"}.get(frame.state, "❓")

    return (
        f"{status_icon} Game {frame.game_no} | {frame.game_time}\n"
        f"  {frame.blue_team}: {frame.blue_kills}击杀 | {frame.blue_towers}塔 | {frame.blue_drakes}龙 | {frame.blue_barons}男爵\n"
        f"  {frame.red_team}: {frame.red_kills}击杀 | {frame.red_towers}塔 | {frame.red_drakes}龙 | {frame.red_barons}男爵\n"
        f"  [{bar}] {frame.blue_kills} - {frame.red_kills}{gold_str}"
    )


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


def format_live_list(matches: list[LiveMatch]) -> str:
    """格式化实时比赛列表。"""
    if not matches:
        return "📡 当前没有正在进行的比赛。"
    lines = [f"📡 实时比赛 ({len(matches)} 场)\n"]
    for i, live in enumerate(matches, 1):
        lines.append(f"{i}. [{live.league_name}] {live.match_name}  ({live.score})  {live.status}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════
#  战队 / 选手 格式化（新端点）
# ═══════════════════════════════════════════════════

def format_team_info(data: dict) -> str:
    """格式化单个战队信息。"""
    name = data.get("name", data.get("code", "未知战队"))
    region = data.get("region", data.get("league", ""))
    slug = data.get("slug", "")
    image = data.get("image", data.get("logoUrl", ""))
    lines = [f"🏢 {name}"]
    if region:
        lines.append(f"赛区: {region}")
    if slug:
        lines.append(f"标识: {slug}")
    if image:
        lines.append(f"队标: {image}")
    return "\n".join(lines)


def format_team_roster(data: dict) -> str:
    """格式化战队阵容。"""
    team_name = data.get("team", {}).get("name", "未知战队") if isinstance(data.get("team"), dict) else data.get("name", "未知战队")
    players = data.get("players", data.get("roster", data.get("data", [])))
    if not players:
        return f"📋 {team_name} 暂无阵容数据。"
    lines = [f"📋 {team_name} 战队阵容\n"]
    
    # 按角色排序：TOP → JUNGLE → MID → ADC → SUPPORT
    ROLE_ORDER = {"top": 0, "jungle": 1, "mid": 2, "adc": 3, "support": 4,
                   "上单": 0, "打野": 1, "中单": 2, "下路": 3, "辅助": 4}
    
    def _role_sort_key(p):
        role = (p.get("role") or p.get("position") or "").strip().lower()
        for k, v in ROLE_ORDER.items():
            if k in role:
                return v
        return 99  # unknown roles at end
    
    sorted_players = sorted(players, key=_role_sort_key)
    
    for p in sorted_players:
        if isinstance(p, str):
            lines.append(f"  {p}")
            continue
        # 提取选手名：支持多种字段名
        name = p.get("name") or p.get("handle") or p.get("summonerName") or p.get("nickname") or ""
        if not name and isinstance(p.get("player"), dict):
            name = p["player"].get("name") or p["player"].get("handle") or "?"
        if not name:
            name = "?"
        # 提取角色
        role = (p.get("role") or p.get("position") or p.get("lane") or "—").strip().upper()
        # 标准化角色名
        role_map = {"TOP": "TOP", "JUNGLE": "JUNGLE", "JUG": "JUNGLE", "JG": "JUNGLE",
                    "MID": "MID", "MIDDLE": "MID", "ADC": "ADC", "BOT": "ADC", "BOTTOM": "ADC",
                    "SUPPORT": "SUPPORT", "SUP": "SUPPORT"}
        role = role_map.get(role, role)
        lines.append(f"  {role:7} | {name}")
    return "\n".join(lines)


def format_team_matches(data: dict) -> str:
    """格式化战队近期比赛。"""
    matches = data.get("matches", data.get("events", []))
    if not matches:
        return "📅 暂无近期比赛数据。"
    lines = [f"📅 近期比赛 ({len(matches)} 场)\n"]
    for m in matches[:10]:
        blue = m.get("blue", m.get("blueTeam", {}))
        red = m.get("red", m.get("redTeam", {}))
        if isinstance(blue, dict):
            blue = blue.get("name", blue.get("code", "蓝方"))
        if isinstance(red, dict):
            red = red.get("name", red.get("code", "红方"))
        status = m.get("status", m.get("state", ""))
        date = m.get("date", m.get("startDate", m.get("startTime", "")))
        winner = m.get("winner", "")
        icon = "✅" if status in ("completed", "finished") else "⏳"
        lines.append(f"{icon} {blue} vs {red}  {winner or ''}  {date}")
    return "\n".join(lines)


def format_player_info(data: dict) -> str:
    """格式化单个选手信息。"""
    name = data.get("name", data.get("handle", "未知选手"))
    team = data.get("team", {})
    if isinstance(team, dict):
        team = team.get("name", team.get("code", ""))
    role = data.get("role", data.get("position", ""))
    nationality = data.get("nationality", data.get("country", ""))
    image = data.get("image", data.get("photoUrl", ""))
    lines = [f"👤 {name}"]
    if team:
        lines.append(f"战队: {team}")
    if role:
        lines.append(f"位置: {role}")
    if nationality:
        lines.append(f"国籍: {nationality}")
    if image:
        lines.append(f"照片: {image}")
    return "\n".join(lines)


def format_player_stats(data: dict) -> str:
    """格式化选手统计数据。"""
    name = data.get("name", data.get("player", {}).get("name", "未知选手") if isinstance(data.get("player"), dict) else "未知选手")
    kda = data.get("kda", "")
    kills = data.get("kills", data.get("avgKills", 0))
    deaths = data.get("deaths", data.get("avgDeaths", 0))
    assists = data.get("assists", data.get("avgAssists", 0))
    cs = data.get("cs", data.get("csPerMin", data.get("cspm", 0)))
    games = data.get("gamesPlayed", data.get("games", 0))
    kp = data.get("killParticipation", data.get("kp", ""))
    lines = [f"📊 {name} 统计数据\n"]
    if kda:
        lines.append(f"KDA: {kda}")
    lines.append(f"场均击杀: {kills}  |  场均死亡: {deaths}  |  场均助攻: {assists}")
    if cs:
        lines.append(f"场均补刀: {cs}")
    if kp:
        lines.append(f"参团率: {kp}")
    lines.append(f"比赛场次: {games}")
    return "\n".join(lines)


def format_player_champions(data: dict) -> str:
    """格式化选手英雄池。"""
    champs = data.get("champions", data.get("mostPlayed", []))
    name = data.get("player", {}).get("name", "") if isinstance(data.get("player"), dict) else ""
    header = f"🎮 {name} 英雄池" if name else "🎮 英雄池"
    if not champs:
        return f"{header}\n暂无数据。"
    lines = [f"{header}\n"]
    for c in champs[:10]:
        champ_name = c.get("champion", c.get("name", "?"))
        games = c.get("games", c.get("gamesPlayed", 0))
        wins = c.get("wins", 0)
        wr = f"{wins / games * 100:.0f}%" if games > 0 else "—"
        lines.append(f"  {champ_name}: {games}场  {wr}胜率")
    return "\n".join(lines)


def format_team_stats(data: dict) -> str:
    """格式化战队统计数据。"""
    # 战队名称提取
    team_name = ""
    if isinstance(data.get("team"), dict):
        team_name = data["team"].get("name", data["team"].get("code", ""))
    if not team_name:
        team_name = data.get("name", data.get("code", "未知战队"))

    lines = [f"📊 {team_name} 统计数据\n"]

    # 战绩
    wins = data.get("wins", data.get("win", 0))
    losses = data.get("losses", data.get("loss", 0))
    games = data.get("gamesPlayed", data.get("games", wins + losses))
    wr_val = data.get("winRate", data.get("wr", 0))
    if not wr_val and games > 0:
        wr_val = wins / games
    wr_str = f"{float(wr_val) * 100:.1f}%" if wr_val else ""
    if games > 0:
        lines.append(f"战绩: {wins}胜 {losses}负  |  胜率: {wr_str}  |  场次: {games}")

    # KDA
    kda = data.get("kda", data.get("avgKda", ""))
    kills = data.get("avgKills", data.get("kills", data.get("avgKillsPerGame", 0)))
    deaths = data.get("avgDeaths", data.get("deaths", data.get("avgDeathsPerGame", 0)))
    assists = data.get("avgAssists", data.get("assists", data.get("avgAssistsPerGame", 0)))
    if kda or kills or deaths:
        if kda:
            lines.append(f"KDA: {kda}")
        lines.append(f"场均击杀: {kills}  |  场均死亡: {deaths}  |  场均助攻: {assists}")

    # 经济/补刀
    gpm = data.get("goldPerMin", data.get("gpm", data.get("avgGoldPerMin", 0)))
    cspm = data.get("csPerMin", data.get("cspm", data.get("avgCsPerMin", 0)))
    if gpm or cspm:
        parts = []
        if gpm:
            parts.append(f"分均经济: {gpm}")
        if cspm:
            parts.append(f"分均补刀: {cspm}")
        lines.append("  |  ".join(parts))

    # 场均时长
    avg_time = data.get("avgGameTime", data.get("avgGameDuration", data.get("avgDuration", "")))
    if avg_time:
        lines.append(f"场均时长: {avg_time}")

    # 目标控制
    barons = data.get("barons", data.get("avgBarons", data.get("totalBarons", 0)))
    drakes = data.get("drakes", data.get("avgDrakes", data.get("dragons", data.get("totalDrakes", 0))))
    towers = data.get("towers", data.get("avgTowers", data.get("totalTowers", 0)))
    if barons or drakes or towers:
        parts = []
        if barons:
            parts.append(f"大龙: {barons}")
        if drakes:
            parts.append(f"小龙: {drakes}")
        if towers:
            parts.append(f"防御塔: {towers}")
        lines.append("  |  ".join(parts))

    # 一血/一塔率
    fb = data.get("firstBloodRate", data.get("firstBlood", data.get("fb", "")))
    ft = data.get("firstTowerRate", data.get("firstTower", data.get("ft", "")))
    if fb or ft:
        parts = []
        if fb:
            parts.append(f"一血率: {fb}")
        if ft:
            parts.append(f"一塔率: {ft}")
        lines.append("  |  ".join(parts))

    return "\n".join(lines)


# ═══════════════════════════════════════════════════
#  锦标赛 / 英雄 / 排行榜 格式化
# ═══════════════════════════════════════════════════

def format_tournament_info(data: dict) -> str:
    """格式化锦标赛信息。"""
    # 如果 API 返回的是列表，取第一个元素
    if isinstance(data, list):
        if not data:
            return "🏆 暂无锦标赛数据。"
        data = data[0] if isinstance(data[0], dict) else {}
        if not isinstance(data, dict):
            return "🏆 暂无锦标赛数据。"

    # 尝试多种嵌套路径
    inner = data.get("tournament", data.get("event", data))
    if isinstance(inner, dict):
        name = inner.get("name", inner.get("title", data.get("name", data.get("title", "未知赛事"))))
        status = inner.get("status", data.get("status", inner.get("state", "")))
        league = inner.get("league", data.get("league", ""))
        season = inner.get("season", data.get("season", ""))
        start = inner.get("startDate", inner.get("start", data.get("startDate", data.get("start", ""))))
        end = inner.get("endDate", inner.get("end", data.get("endDate", data.get("end", ""))))
        # league 可能是 dict
        if isinstance(league, dict):
            league = league.get("name", league.get("slug", ""))
    else:
        name = data.get("name", data.get("title", "未知赛事"))
        status = data.get("status", data.get("state", ""))
        league = data.get("league", "")
        season = data.get("season", "")
        start = data.get("startDate", data.get("start", ""))
        end = data.get("endDate", data.get("end", ""))
    lines = [f"🏆 {name}"]
    if league:
        lines.append(f"联赛: {league}")
    if season:
        lines.append(f"赛季: {season}")
    if status:
        lines.append(f"状态: {status}")
    if start:
        lines.append(f"开始: {start}")
    if end:
        lines.append(f"结束: {end}")
    return "\n".join(lines)


def format_tournament_standings(data: dict) -> str:
    """格式化锦标赛积分榜。"""
    standings = data.get("standings", data.get("results", []))
    if not standings:
        return "📊 暂无积分榜数据。"
    name = data.get("name", "")
    lines = [f"📊 {name} 积分榜\n" if name else "📊 积分榜\n"]
    for i, s in enumerate(standings[:20], 1):
        team = s.get("team", {})
        if isinstance(team, dict):
            team = team.get("name", team.get("code", "?"))
        w = s.get("wins", 0)
        l = s.get("losses", 0)
        pts = s.get("points", 0)
        lines.append(f"  {i:>2}. {team}  {w}胜-{l}负  {pts}分")
    return "\n".join(lines)


def format_tournament_bracket(data: dict) -> str:
    """格式化锦标赛淘汰赛对阵。"""
    bracket = data.get("bracket", data)
    if not bracket:
        return "🏆 暂无淘汰赛对阵数据。"
    lines = ["🏆 淘汰赛对阵\n"]
    rounds = bracket.get("rounds", bracket.get("stages", []))
    for r in rounds:
        rname = r.get("name", r.get("round", ""))
        if rname:
            lines.append(f"━━ {rname} ━━")
        for m in r.get("matches", []):
            t1 = m.get("team1", m.get("teamA", {}))
            t2 = m.get("team2", m.get("teamB", {}))
            if isinstance(t1, dict):
                t1 = t1.get("name", t1.get("code", "?"))
            if isinstance(t2, dict):
                t2 = t2.get("name", t2.get("code", "?"))
            winner = m.get("winner", "")
            lines.append(f"  {t1} vs {t2}  → {winner}" if winner else f"  {t1} vs {t2}")
    return "\n".join(lines)


def format_tournament_mvp(data: dict) -> str:
    """格式化锦标赛 MVP。"""
    mvp = data.get("mvp", data)
    if isinstance(mvp, list):
        if not mvp:
            return "🏅 暂无 MVP 数据。"
        lines = ["🏅 MVP 列表\n"]
        for m in mvp[:10]:
            name = m.get("name", m.get("player", "?"))
            team = m.get("team", "")
            lines.append(f"  {name}" + (f" ({team})" if team else ""))
        return "\n".join(lines)
    name = mvp.get("name", mvp.get("player", "?"))
    team = mvp.get("team", "")
    return f"🏅 MVP: {name}" + (f" ({team})" if team else "")


def format_champion_stats(data: dict, limit: int = 10) -> str:
    """格式化英雄统计。"""
    if isinstance(data, list):
        champs = data
    else:
        champs = (data.get("champions") or data.get("data") or data.get("results") or [])
        if isinstance(champs, dict):
            champs = (champs.get("champions") or champs.get("data") or [])
    if not champs:
        return "🎮 暂无英雄统计数据。"
    lines = ["🎮 英雄统计\n"]
    for c in champs[:limit]:
        name = c.get("champion", c.get("name", "?"))
        games = c.get("games", c.get("gamesPlayed", 0))
        wins = c.get("wins", 0)
        kda = c.get("kda", "")
        wr = f"{wins / games * 100:.1f}%" if isinstance(games, (int, float)) and games > 0 else "—"
        parts = [f"  {name}: {games}场  {wr}"]
        if kda:
            parts.append(f"KDA {kda}")
        lines.append("  |  ".join(parts))
    return "\n".join(lines)


def format_champion_presence(data: dict, limit: int = 10) -> str:
    """格式化英雄 Pick/Ban 率。"""
    champs = data.get("champions", data.get("data", []))
    if not champs:
        return "📋 暂无 Pick/Ban 数据。"
    lines = ["📋 英雄 Pick/Ban 率\n"]
    for c in champs[:limit]:
        name = c.get("champion", c.get("name", "?"))
        presence = c.get("presence", c.get("presenceRate", c.get("pb", "")))
        pick = c.get("pick", c.get("pickRate", ""))
        ban = c.get("ban", c.get("banRate", ""))
        lines.append(f"  {name}: P/B {presence}")
        if pick:
            lines[-1] += f"  (P:{pick} B:{ban})"
    return "\n".join(lines)


# ═══════════════════════════════════════════════════
#  排行榜 / 搜索 / 趋势 格式化
# ═══════════════════════════════════════════════════

def format_gpr_rankings(data: dict, limit: int = 20) -> str:
    """格式化全球战力排名。"""
    if isinstance(data, list):
        rankings = data
    else:
        rankings = (data.get("rankings") or data.get("teams") or data.get("data") or [])
        if isinstance(rankings, dict):
            rankings = (rankings.get("rankings") or rankings.get("teams") or [])
    if not rankings:
        return "🌍 暂无全球战力排名数据。"
    lines = [f"🌍 全球战力排名 (Top {min(limit, len(rankings))})\n"]
    for i, r in enumerate(rankings[:limit], 1):
        team = r.get("team", r.get("name", "?"))
        if isinstance(team, dict):
            team = team.get("name", team.get("code", "?"))
        pts = r.get("points", r.get("score", r.get("rating", "")))
        lines.append(f"  {i:>2}. {team}  {pts}")
    return "\n".join(lines)


def format_player_rankings(data: dict, metric: str = "kda", limit: int = 15) -> str:
    """格式化选手排名。"""
    rankings = data.get("rankings", data.get("players", data.get("data", [])))
    if not rankings:
        return f"📊 暂无{metric}排名数据。"
    lines = [f"📊 选手{metric.upper()}排名 (Top {min(limit, len(rankings))})\n"]
    for i, r in enumerate(rankings[:limit], 1):
        name = r.get("player", r.get("name", "?"))
        if isinstance(name, dict):
            name = name.get("name", name.get("handle", "?"))
        val = r.get("value", r.get(metric, r.get("score", "")))
        team = r.get("team", "")
        if isinstance(team, dict):
            team = team.get("name", team.get("code", ""))
        entry = f"  {i:>2}. {name}"
        if team:
            entry += f" ({team})"
        entry += f" — {val}"
        lines.append(entry)
    return "\n".join(lines)


def format_leaderboard(data: dict, metric: str = "", limit: int = 15) -> str:
    """格式化通用排行榜（KDA/击杀/死亡/助攻/补刀/经济/视野/伤害）。"""
    entries = data.get("leaderboard", data.get("rankings", data.get("players", data.get("data", []))))
    if not entries:
        return f"📊 暂无{metric}排行榜数据。"
    label = metric.upper() if metric else "数据"
    lines = [f"📊 {label}排行榜 (Top {min(limit, len(entries))})\n"]
    for i, entry in enumerate(entries[:limit], 1):
        player = entry.get("player", entry.get("name", "?"))
        if isinstance(player, dict):
            player = player.get("name", player.get("handle", "?"))
        val = entry.get("value", entry.get("score", entry.get(metric.lower(), "")))
        team = entry.get("team", "")
        if isinstance(team, dict):
            team = team.get("name", team.get("code", ""))
        parts = [player]
        if team:
            parts.append(f"({team})")
        parts.append(str(val))
        lines.append(f"  {i:>2}. {' '.join(parts)}")
    return "\n".join(lines)


def format_search_teams(data: dict) -> str:
    """格式化战队搜索结果。"""
    # 处理包装后的数据
    if isinstance(data, list):
        teams = data
    else:
        teams = (data.get("teams") or data.get("results") or data.get("data") or [])
        if isinstance(teams, dict):
            teams = teams.get("teams") or teams.get("results") or teams.get("data") or []
    if not teams:
        return "🔍 未找到匹配的战队。\n💡 提示：尝试使用英文全称（如 T1、GenG），或使用 /lol team info <全名>"
    lines = [f"🔍 战队搜索结果 ({len(teams)} 条)\n"]
    for t in teams[:10]:
        if isinstance(t, str):
            lines.append(f"  {t}")
            continue
        name = t.get("name") or t.get("code") or t.get("team") or "?"
        if isinstance(name, dict):
            name = name.get("name") or name.get("code") or "?"
        region = (t.get("region") or t.get("league") or t.get("country") or "")
        if isinstance(region, dict):
            region = region.get("name") or region.get("slug") or ""
        sid = t.get("id") or t.get("teamId") or t.get("slug") or ""
        line = f"  {name}"
        if region:
            line += f" ({region})"
        if sid:
            line += f"  [{sid}]"
        lines.append(line)
    return "\n".join(lines)


def format_search_players(data: dict) -> str:
    """格式化选手搜索结果。"""
    # 处理包装后的数据
    if isinstance(data, list):
        players = data
    else:
        players = (data.get("players") or data.get("results") or data.get("data") or [])
        if isinstance(players, dict):
            players = players.get("players") or players.get("results") or players.get("data") or []
    if not players:
        return "🔍 未找到匹配的选手。\n💡 提示：尝试使用英文 ID（如 Faker、Chovy），确保大小写正确"
    lines = [f"🔍 选手搜索结果 ({len(players)} 条)\n"]
    for p in players[:10]:
        if isinstance(p, str):
            lines.append(f"  {p}")
            continue
        name = (p.get("name") or p.get("handle") or p.get("summonerName") or 
                p.get("nickname") or p.get("player") or "?")
        if isinstance(name, dict):
            name = name.get("name") or name.get("handle") or "?"
        team = p.get("team") or p.get("teamName") or ""
        if isinstance(team, dict):
            team = team.get("name") or team.get("code") or ""
        rid = p.get("id") or p.get("playerId") or p.get("slug") or ""
        parts = [f"  {name}"]
        if team:
            parts.append(f"({team})")
        if rid:
            parts.append(f"[{rid}]")
        lines.append(" ".join(parts))
    return "\n".join(lines)


def format_trending(data: dict) -> str:
    """格式化热门趋势。"""
    if not data:
        return "🔥 暂无热门趋势数据。"
    lines = ["🔥 热门趋势\n"]
    for key, items in data.items():
        if isinstance(items, list) and items:
            label = {"teams": "热门战队", "players": "热门选手", "matches": "热门比赛",
                     "champions": "热门英雄", "tournaments": "热门赛事"}.get(key, key)
            lines.append(f"━━ {label} ({len(items)}) ━━")
            for item in items[:5]:
                if isinstance(item, dict):
                    name = item.get("name") or item.get("team") or item.get("player") or item.get("champion") or item.get("title") or ""
                    if isinstance(name, dict):
                        name = name.get("name") or name.get("code") or "?"
                    # 附加信息
                    extra = ""
                    if "score" in item:
                        extra = f" — {item['score']}"
                    elif "points" in item:
                        extra = f" — {item['points']}"
                    elif "kda" in item:
                        extra = f" — KDA {item['kda']}"
                    lines.append(f"  {name}{extra}")
                elif isinstance(item, str):
                    lines.append(f"  {item}")
            lines.append("")
    if len(lines) == 1:
        lines[0] = "🔥 暂无热门趋势数据。"
    return "\n".join(lines)


# ═══════════════════════════════════════════════════
#  历史 / 转会 / 记录 格式化
# ═══════════════════════════════════════════════════

def format_history(data: dict, title: str = "历史数据") -> str:
    """格式化历史赛事数据。"""
    # 如果 API 直接返回列表
    if isinstance(data, list):
        winners = data
    else:
        # 尝试多种数据路径
        winners = (data.get("winners") or data.get("results") or 
                   data.get("data") or data.get("history") or data.get("tournaments") or [])
        if isinstance(winners, dict):
            # 可能在 data 包裹里
            winners = (winners.get("winners") or winners.get("results") or 
                       winners.get("history") or winners.get("tournaments") or [])

    if not winners:
        return f"📜 {title}: 暂无数据。"
    lines = [f"📜 {title}\n"]
    for w in winners[:15]:
        if isinstance(w, dict):
            year = (w.get("year") or w.get("season") or w.get("edition") or "")
            team = (w.get("winner") or w.get("team") or w.get("name") or 
                    w.get("champion") or w.get("title") or "?")
            if isinstance(team, dict):
                team = (team.get("name") or team.get("code") or team.get("team") or "?")
            # 如果 team 仍是 None，尝试其他路径
            if team == "?" or team is None:
                # 尝试从 result 路径提取
                result = w.get("result", {})
                if isinstance(result, dict):
                    team = result.get("winner") or result.get("team") or "?"
            if not team or team == "None":
                team = "?"
            lines.append(f"  {year}: {team}")
        elif isinstance(w, str):
            lines.append(f"  {w}")
    return "\n".join(lines)


def format_transfers(data: dict) -> str:
    """格式化转会信息。"""
    # 处理 API 直接返回列表的情况
    if isinstance(data, list):
        transfers = data
    else:
        transfers = data.get("transfers", data.get("data", data.get("players", data.get("results", []))))
    if not transfers:
        return "🔄 暂无转会数据。"
    lines = [f"🔄 转会信息 ({len(transfers)} 条)\n"]
    for t in transfers[:15]:
        if not isinstance(t, dict):
            lines.append(f"  {t}")
            continue
        # 提取选手名：支持多种格式
        player = (t.get("player") or t.get("name") or t.get("playerName") or 
                  t.get("summonerName") or t.get("handle") or "")
        if isinstance(player, dict):
            player = player.get("name") or player.get("handle") or player.get("summonerName") or "?"
        if not player:
            player = "?"
        
        # 提取来源战队
        from_team = (t.get("from") or t.get("fromTeam") or t.get("from_team") or 
                     t.get("previousTeam") or t.get("oldTeam") or "")
        if isinstance(from_team, dict):
            from_team = from_team.get("name") or from_team.get("code") or ""
        
        # 提取目标战队
        to_team = (t.get("to") or t.get("toTeam") or t.get("to_team") or 
                   t.get("newTeam") or t.get("currentTeam") or "")
        if isinstance(to_team, dict):
            to_team = to_team.get("name") or to_team.get("code") or ""
        
        # 提取日期/赛季
        date = t.get("date") or t.get("season") or t.get("year") or ""
        
        line = f"  {player}"
        if from_team or to_team:
            line += f": {from_team} → {to_team}"
        if date:
            line += f"  ({date})"
        lines.append(line)
    return "\n".join(lines)


def format_records(data: dict) -> str:
    """格式化赛事记录/里程碑。"""
    # 处理 API 直接返回列表的情况
    if isinstance(data, list):
        records = data
    else:
        records = data.get("records", data.get("data", data.get("milestones", [])))
    if not records:
        return "🏅 暂无赛事记录。"
    lines = ["🏅 赛事记录\n"]
    for r in records[:15]:
        if not isinstance(r, dict):
            lines.append(f"  {r}")
            continue
        title = r.get("title", r.get("record", r.get("description", "")))
        holder = r.get("holder", r.get("player", r.get("team", "")))
        val = r.get("value", r.get("score", ""))
        line = f"  {title}"
        if holder:
            line += f" — {holder}"
        if val:
            line += f" ({val})"
        lines.append(line)
    return "\n".join(lines)


def format_json_result(data: Any, title: str = "结果") -> str:
    """通用 JSON 格式化（fallback）。"""
    import json
    if isinstance(data, dict):
        return f"{title}:\n{json.dumps(data, ensure_ascii=False, indent=2)}"
    if isinstance(data, (list, str, int, float)):
        return f"{title}: {data}"
    return f"{title}: (无数据)"
