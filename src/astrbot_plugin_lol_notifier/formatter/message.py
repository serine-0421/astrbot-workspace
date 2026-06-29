"""Text formatter for LoL notifications."""

from __future__ import annotations

from typing import Any

from ..models import LeagueMatch, LiveGameFrame, LiveMatch, MatchDetail, MatchGame, StandingEntry
from ..utils import replace_side_mentions


def format_schedule(matches: list[LeagueMatch], limit: int = 5) -> str:
    if not matches:
        return "📅 暂无比赛安排。"
    # 按日期降序排列（最近的在前面）
    def _sort_key(m: LeagueMatch):
        d = (m.start_date or "") + (m.start_time or "")
        return d if d else "0000"
    sorted_matches = sorted(matches, key=_sort_key, reverse=True)
    lines = ["📅 LoL 近期赛程（最近优先）\n"]
    for match in sorted_matches[:limit]:
        teams = " vs ".join(match.teams) if match.teams else match.match_name or "未知对局"
        round_info = f"第{match.round}场 " if match.round else ""
        lines.append(
            f"[{match.league.upper()} · {match.stage}] {round_info}{teams}\n"
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
    if match.match_id:
        lines.append(f"\n💡 使用 /lol detail {match.league} {match.round or match.match_id} 查看详细对局数据")
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


def format_player_stats(data: dict) -> str:
    """格式化选手统计数据。"""
    inner = data.get("data", data)
    if not isinstance(inner, dict):
        inner = data
    # 多方尝试提取名字
    name = (
        inner.get("name")
        or inner.get("handle")
        or inner.get("summonerName")
        or inner.get("summoner_name")
        or inner.get("ign")
        or inner.get("nickname")
        or inner.get("playerName")
        or (inner.get("player", {}) if isinstance(inner.get("player"), dict) else {}).get("name")
        or "未知选手"
    )
    kda = inner.get("kda", inner.get("KDA", ""))
    kills = inner.get("kills", inner.get("avgKills", inner.get("averageKills", inner.get("avg_kills", 0))))
    deaths = inner.get("deaths", inner.get("avgDeaths", inner.get("averageDeaths", inner.get("avg_deaths", 0))))
    assists = inner.get("assists", inner.get("avgAssists", inner.get("averageAssists", inner.get("avg_assists", 0))))
    cs = inner.get("cs", inner.get("csPerMin", inner.get("cspm", inner.get("csPerMinute", 0))))
    games = inner.get("gamesPlayed", inner.get("games", inner.get("totalGames", 0)))
    kp = inner.get("killParticipation", inner.get("kp", inner.get("killParticipationRate", "")))
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


def format_player_earnings(data: dict) -> str:
    """格式化选手奖金汇总。"""
    if isinstance(data, list):
        data = data[0] if data else {}
    name = (
        data.get("playerName") or data.get("name") or data.get("handle")
        or data.get("summonerName") or ""
    )
    if isinstance(name, dict):
        name = name.get("name") or name.get("handle") or "?"
    total = data.get("totalEarnings", data.get("total", data.get("earnings", data.get("amount", 0))))
    currency = data.get("currency", "USD")
    top_pay = data.get("highestTournamentEarnings", data.get("highest", ""))
    years = data.get("yearsActive", data.get("years", ""))
    teams_count = data.get("teamsCount", data.get("teamsPlayed", ""))
    lines = [f"💰 {name} 生涯奖金"] if name else ["💰 选手生涯奖金"]
    lines.append(f"总奖金: ${total:,.2f} {currency}" if isinstance(total, (int, float)) else f"总奖金: {total} {currency}")
    if top_pay:
        lines.append(f"单赛事最高: ${top_pay:,.2f}" if isinstance(top_pay, (int, float)) else f"单赛事最高: {top_pay}")
    if years:
        lines.append(f"活跃年份: {years}")
    if teams_count:
        lines.append(f"效力战队: {teams_count}")
    return "\n".join(lines)


def format_transfers_player(data: dict) -> str:
    """格式化选手转会历史。"""
    if isinstance(data, list):
        transfers = data
    else:
        transfers = data.get("transfers", data.get("data", data.get("results", [])))
    if not transfers:
        return "🔄 暂无该选手转会数据。"
    lines = ["🔄 选手转会历史\n"]
    for t in transfers[:20]:
        if isinstance(t, str):
            lines.append(f"  {t}")
            continue
        player = t.get("player", t.get("name", ""))
        if isinstance(player, dict):
            player = player.get("name", player.get("handle", "?"))
        from_team = t.get("from", t.get("fromTeam", t.get("from_team", "")))
        if isinstance(from_team, dict):
            from_team = from_team.get("name", from_team.get("code", ""))
        to_team = t.get("to", t.get("toTeam", t.get("to_team", "")))
        if isinstance(to_team, dict):
            to_team = to_team.get("name", to_team.get("code", ""))
        date = t.get("date", t.get("season", t.get("year", "")))
        line = f"  {from_team} → {to_team}" if from_team or to_team else ""
        if player and line:
            line = f"  {player}: {line[3:]}"
        elif player:
            line = f"  {player}"
        if date:
            line += f"  ({date})"
        lines.append(line)
    return "\n".join(lines)


def format_transfers_team(data: dict) -> str:
    """格式化战队转会记录。"""
    if isinstance(data, list):
        transfers = data
    else:
        transfers = data.get("transfers", data.get("data", data.get("results", [])))
    if not transfers:
        return "🔄 暂无该战队转会数据。"
    lines = ["🔄 战队转会记录\n"]
    for t in transfers[:20]:
        if isinstance(t, str):
            lines.append(f"  {t}")
            continue
        player = t.get("player", t.get("name", ""))
        if isinstance(player, dict):
            player = player.get("name", player.get("handle", "?"))
        direction = t.get("direction", t.get("type", ""))  # in/out
        team = t.get("team", t.get("from", t.get("to", "")))
        if isinstance(team, dict):
            team = team.get("name", team.get("code", ""))
        date = t.get("date", t.get("season", t.get("year", "")))
        icon = "🔴 离队" if direction and direction.lower() in ("out", "leave", "sell") else "🟢 入队"
        line = f"  {icon}: {player}"
        if team:
            line += f"  [{team}]"
        if date:
            line += f"  ({date})"
        lines.append(line)
    return "\n".join(lines)


def format_coverage(data: dict) -> str:
    """格式化直播覆盖矩阵。"""
    if not data or not isinstance(data, dict):
        return "📡 暂无直播覆盖数据。"
    lines = ["📡 直播覆盖矩阵\n"]
    leagues = data.get("leagues", data.get("data", {}))
    if isinstance(leagues, list):
        for league in leagues[:10]:
            if isinstance(league, dict):
                name = league.get("name", league.get("league", "?"))
                platforms = league.get("platforms", league.get("streams", []))
                lines.append(f"  {name}: {', '.join(platforms) if platforms else '无'}")
            else:
                lines.append(f"  {league}")
    elif isinstance(leagues, dict):
        for league_name, platforms in leagues.items():
            if isinstance(platforms, list):
                lines.append(f"  {league_name}: {', '.join(platforms)}")
            else:
                lines.append(f"  {league_name}: {platforms}")
    if len(lines) == 1:
        lines.append("(暂无)" if not data else str(data)[:200])
    return "\n".join(lines)


