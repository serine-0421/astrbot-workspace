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


