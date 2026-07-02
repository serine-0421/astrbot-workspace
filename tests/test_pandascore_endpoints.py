import asyncio

from src.astrbot_plugin_lol_notifier.fetcher import pandascore


def test_fetch_champions_sends_version_filter_for_all(monkeypatch) -> None:
    calls: list[tuple[str, dict | None]] = []

    async def fake_ps_call(endpoint: str, params: dict | None = None):
        calls.append((endpoint, params))
        return pandascore.Success(value={"data": []})

    monkeypatch.setattr(pandascore, "_ps_call", fake_ps_call)

    asyncio.run(pandascore.fetch_champions(version="all"))

    assert calls == [
        (
            "/lol/champions",
            {"page": 1, "per_page": 50, "filter[videogame_version]": "all"},
        )
    ]


def test_fetch_items_sends_version_filter_for_all(monkeypatch) -> None:
    calls: list[tuple[str, dict | None]] = []

    async def fake_ps_call(endpoint: str, params: dict | None = None):
        calls.append((endpoint, params))
        return pandascore.Success(value={"data": []})

    monkeypatch.setattr(pandascore, "_ps_call", fake_ps_call)

    asyncio.run(pandascore.fetch_items(version="all"))

    assert calls == [
        (
            "/lol/items",
            {"page": 1, "per_page": 50, "filter[videogame_version]": "all"},
        )
    ]


def test_fetch_matches_uses_status_specific_endpoint(monkeypatch) -> None:
    calls: list[tuple[str, dict | None]] = []

    async def fake_ps_call(endpoint: str, params: dict | None = None):
        calls.append((endpoint, params))
        return pandascore.Success(value={"data": []})

    async def fake_resolve_league_id(user_slug: str) -> int | None:
        return 12345  # dummy league id

    monkeypatch.setattr(pandascore, "_ps_call", fake_ps_call)
    monkeypatch.setattr(pandascore, "_resolve_league_id", fake_resolve_league_id)

    asyncio.run(pandascore.fetch_matches(league="lpl", status="upcoming"))

    assert calls[0][0] == "/lol/matches/upcoming"
    assert calls[0][1]["filter[league_id]"] == 12345


def test_fetch_series_and_tournaments_use_status_suffixes(monkeypatch) -> None:
    calls: list[tuple[str, dict | None]] = []

    async def fake_ps_call(endpoint: str, params: dict | None = None):
        calls.append((endpoint, params))
        return pandascore.Success(value={"data": []})

    async def fake_resolve_league_id(user_slug: str) -> int | None:
        return 67890  # dummy league id

    monkeypatch.setattr(pandascore, "_ps_call", fake_ps_call)
    monkeypatch.setattr(pandascore, "_resolve_league_id", fake_resolve_league_id)

    asyncio.run(pandascore.fetch_series_list(league="lpl", status="running"))
    asyncio.run(pandascore.fetch_tournaments(league="lpl", status="past"))

    assert calls[0][0] == "/lol/series/running"
    assert calls[1][0] == "/lol/tournaments/past"
    assert calls[0][1]["filter[league_id]"] == 67890
    assert calls[1][1]["filter[league_id]"] == 67890


def test_fetch_game_and_match_extensions_use_expected_routes(monkeypatch) -> None:
    calls: list[tuple[str, dict | None]] = []

    async def fake_ps_call(endpoint: str, params: dict | None = None):
        calls.append((endpoint, params))
        return pandascore.Success(value={"data": []})

    monkeypatch.setattr(pandascore, "_ps_call", fake_ps_call)

    asyncio.run(pandascore.fetch_game_detail("1001"))
    asyncio.run(pandascore.fetch_game_events("1001"))
    asyncio.run(pandascore.fetch_game_frames("1001"))
    asyncio.run(pandascore.fetch_match_games("2001"))
    asyncio.run(pandascore.fetch_match_players_stats("2001"))
    asyncio.run(pandascore.fetch_team_stats("3001"))

    assert calls[0][0] == "/lol/games/1001"
    assert calls[1][0] == "/lol/games/1001/events"
    assert calls[2][0] == "/lol/games/1001/frames"
    assert calls[3][0] == "/lol/matches/2001/games"
    assert calls[4][0] == "/lol/matches/2001/players/stats"
    assert calls[5][0] == "/lol/teams/3001/stats"
