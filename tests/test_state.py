from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path

from photosorg.models import Membership
from photosorg.state import SCHEMA_VERSION, StateStore, new_run_id


def test_schema_and_version(tmp_path: Path) -> None:
    path = tmp_path / "deep" / "state.sqlite3"
    StateStore(path).close()
    db = sqlite3.connect(path)
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {
        "runs",
        "memberships",
        "albums",
        "processed",
        "trips",
        "suggested_events",
        "keywords",
        "meta",
    } <= tables
    assert db.execute("SELECT value FROM meta").fetchone()[0] == str(SCHEMA_VERSION)


def test_reopening_keeps_data(tmp_path: Path) -> None:
    path = tmp_path / "s.sqlite3"
    s = StateStore(path)
    s.start_run("r1")
    s.record_memberships("r1", [Membership("A", "u1")])
    s.finish_run("r1", "ok", datetime(2026, 1, 1, tzinfo=UTC), 1)
    s.close()
    again = StateStore(path)
    assert again.memberships() == {Membership("A", "u1")}
    assert again.high_water() == datetime(2026, 1, 1, tzinfo=UTC)


def test_memberships_are_unique(state: StateStore) -> None:
    state.start_run("r1")
    assert state.record_memberships("r1", [Membership("A", "u"), Membership("A", "u")]) == 1
    assert state.record_memberships("r1", [Membership("A", "u")]) == 0


def test_trip_upsert_widens_dates(state: StateStore) -> None:
    state.start_run("r1")
    state.upsert_trip("r1", "T", date(2026, 5, 2), date(2026, 5, 3), "Paris")
    state.upsert_trip("r1", "T", date(2026, 5, 1), date(2026, 5, 2), "Paris")
    [t] = state.known_trips()
    assert (t.start, t.end) == (date(2026, 5, 1), date(2026, 5, 3))


def test_run_ids_sort_by_time() -> None:
    a = new_run_id(datetime(2026, 1, 1, tzinfo=UTC))
    b = new_run_id(datetime(2026, 1, 2, tzinfo=UTC))
    assert a < b and a.startswith("20260101T000000Z-")
