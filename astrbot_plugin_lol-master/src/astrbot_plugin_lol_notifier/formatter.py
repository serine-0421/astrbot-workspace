"""Text formatter for LoL esports notifications."""

from __future__ import annotations

from .models import LeagueMatch, MatchDetail, MatchGame, StandingEntry


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
        for entry in game.bp:
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
