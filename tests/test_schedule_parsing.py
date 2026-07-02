from datetime import datetime, timedelta, timezone

from src.astrbot_plugin_lol_notifier.fetcher.pandascore import (
    _filter_placeholder_matches,
    _parse_schedule_datetime,
)
from src.astrbot_plugin_lol_notifier.models import LeagueMatch


def test_parse_schedule_datetime_defaults_to_utc_for_naive_strings() -> None:
    dt = _parse_schedule_datetime("2026-07-03T11:00:00")

    assert dt == datetime(2026, 7, 3, 19, 0, tzinfo=timezone(timedelta(hours=8)))


def test_filter_placeholder_matches_removes_tbd_entries() -> None:
    matches = [
        LeagueMatch(
            league="MSI",
            stage="Playoffs",
            round="Knockouts",
            match_id="1",
            match_name="",
            start_date="2026-07-03",
            start_time="11:00",
            status="upcoming",
            teams=["TBD", "TBD"],
            games=[],
            summary="TBD vs TBD",
        ),
        LeagueMatch(
            league="MSI",
            stage="Playoffs",
            round="Knockouts",
            match_id="2",
            match_name="",
            start_date="2026-07-03",
            start_time="16:00",
            status="upcoming",
            teams=["BLG", "T1"],
            games=[],
            summary="BLG vs T1",
        ),
    ]

    filtered = _filter_placeholder_matches(matches)

    assert len(filtered) == 1
    assert filtered[0].teams == ["BLG", "T1"]
