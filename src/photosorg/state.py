"""SQLite state: what every run did, so the next run does only what is missing and undo is exact."""

from __future__ import annotations

import secrets
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from photosorg.models import Membership
from photosorg.trips import KnownTrip

DEFAULT_STATE_PATH = Path("~/Library/Application Support/photosorg/state.sqlite3").expanduser()
SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL CHECK (status IN ('running', 'ok', 'failed', 'undone')),
    high_water TEXT,
    added INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS memberships (
    album TEXT NOT NULL,
    uuid TEXT NOT NULL,
    run_id TEXT NOT NULL REFERENCES runs(id),
    PRIMARY KEY (album, uuid)
);
CREATE TABLE IF NOT EXISTS albums (
    name TEXT PRIMARY KEY,
    created_by_run TEXT REFERENCES runs(id)
);
CREATE TABLE IF NOT EXISTS processed (
    uuid TEXT PRIMARY KEY,
    first_run_id TEXT NOT NULL REFERENCES runs(id)
);
CREATE TABLE IF NOT EXISTS trips (
    name TEXT PRIMARY KEY,
    start_day TEXT NOT NULL,
    end_day TEXT NOT NULL,
    city TEXT NOT NULL,
    run_id TEXT NOT NULL REFERENCES runs(id)
);
CREATE TABLE IF NOT EXISTS suggested_events (
    event TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id)
);
CREATE TABLE IF NOT EXISTS keywords (
    uuid TEXT NOT NULL,
    keyword TEXT NOT NULL,
    run_id TEXT NOT NULL REFERENCES runs(id),
    PRIMARY KEY (uuid, keyword)
);
CREATE INDEX IF NOT EXISTS memberships_run ON memberships(run_id);
"""


def new_run_id(now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    return f"{now.strftime('%Y%m%dT%H%M%SZ')}-{secrets.token_hex(3)}"


@dataclass(frozen=True, slots=True)
class RunRecord:
    id: str
    started_at: str
    finished_at: str | None
    status: str
    added: int


class StateStore:
    def __init__(self, path: Path | str = ":memory:") -> None:
        if isinstance(path, Path):
            path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.db = sqlite3.connect(str(path))
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript(SCHEMA)
        self.db.execute(
            "INSERT OR IGNORE INTO meta VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),)
        )
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self.db:
            yield self.db

    # Runs ----------------------------------------------------------------------------------
    def start_run(self, run_id: str, now: datetime | None = None) -> None:
        ts = (now or datetime.now(UTC)).isoformat()
        with self.transaction() as db:
            db.execute(
                "INSERT INTO runs (id, started_at, status) VALUES (?, ?, 'running')", (run_id, ts)
            )

    def finish_run(self, run_id: str, status: str, high_water: datetime | None, added: int) -> None:
        with self.transaction() as db:
            db.execute(
                "UPDATE runs SET finished_at = ?, status = ?, high_water = ?, added = ? "
                "WHERE id = ?",
                (
                    datetime.now(UTC).isoformat(),
                    status,
                    high_water.isoformat() if high_water else None,
                    added,
                    run_id,
                ),
            )

    def runs(self) -> list[RunRecord]:
        rows = self.db.execute(
            "SELECT id, started_at, finished_at, status, added FROM runs ORDER BY started_at, id"
        )
        return [RunRecord(*r) for r in rows]

    def get_run(self, run_id: str) -> RunRecord | None:
        row = self.db.execute(
            "SELECT id, started_at, finished_at, status, added FROM runs WHERE id = ?", (run_id,)
        ).fetchone()
        return RunRecord(*row) if row else None

    def high_water(self) -> datetime | None:
        row = self.db.execute("SELECT MAX(high_water) FROM runs WHERE status = 'ok'").fetchone()
        return datetime.fromisoformat(row[0]) if row and row[0] else None

    # Memberships ---------------------------------------------------------------------------
    def memberships(self) -> set[Membership]:
        return {Membership(a, u) for a, u in self.db.execute("SELECT album, uuid FROM memberships")}

    def record_album(self, name: str, created_by_run: str | None) -> None:
        with self.transaction() as db:
            db.execute("INSERT OR IGNORE INTO albums VALUES (?, ?)", (name, created_by_run))

    def known_albums(self) -> set[str]:
        return {r[0] for r in self.db.execute("SELECT name FROM albums")}

    def record_memberships(self, run_id: str, items: Iterable[Membership]) -> int:
        with self.transaction() as db:
            cur = db.executemany(
                "INSERT OR IGNORE INTO memberships VALUES (?, ?, ?)",
                [(m.album, m.uuid, run_id) for m in items],
            )
            return cur.rowcount

    def record_processed(self, run_id: str, uuids: Iterable[str]) -> None:
        with self.transaction() as db:
            db.executemany(
                "INSERT OR IGNORE INTO processed VALUES (?, ?)", [(u, run_id) for u in uuids]
            )

    # Trips and suggestions -----------------------------------------------------------------
    def known_trips(self) -> list[KnownTrip]:
        rows = self.db.execute(
            "SELECT name, start_day, end_day, city FROM trips ORDER BY start_day, name"
        )
        return [
            KnownTrip(n, date.fromisoformat(s), date.fromisoformat(e), c) for n, s, e, c in rows
        ]

    def upsert_trip(self, run_id: str, name: str, start: date, end: date, city: str) -> None:
        with self.transaction() as db:
            db.execute(
                "INSERT INTO trips VALUES (?, ?, ?, ?, ?) ON CONFLICT(name) DO UPDATE SET "
                "start_day = MIN(start_day, excluded.start_day), "
                "end_day = MAX(end_day, excluded.end_day)",
                (name, start.isoformat(), end.isoformat(), city, run_id),
            )

    def suggested_events(self) -> set[str]:
        return {r[0] for r in self.db.execute("SELECT event FROM suggested_events")}

    def record_suggested_events(self, run_id: str, events: Iterable[str]) -> None:
        with self.transaction() as db:
            db.executemany(
                "INSERT OR IGNORE INTO suggested_events VALUES (?, ?)",
                [(e, run_id) for e in events],
            )

    def record_keywords(self, run_id: str, uuids: Iterable[str], keyword: str) -> None:
        with self.transaction() as db:
            db.executemany(
                "INSERT OR IGNORE INTO keywords VALUES (?, ?, ?)",
                [(u, keyword, run_id) for u in uuids],
            )

    # Undo ----------------------------------------------------------------------------------
    def run_memberships(self, run_id: str) -> list[Membership]:
        rows = self.db.execute(
            "SELECT album, uuid FROM memberships WHERE run_id = ? ORDER BY album, uuid", (run_id,)
        )
        return [Membership(a, u) for a, u in rows]

    def run_keywords(self, run_id: str) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for uuid, kw in self.db.execute(
            "SELECT uuid, keyword FROM keywords WHERE run_id = ? ORDER BY uuid", (run_id,)
        ):
            out.setdefault(kw, []).append(uuid)
        return out

    def albums_created_by(self, run_id: str) -> set[str]:
        rows = self.db.execute("SELECT name FROM albums WHERE created_by_run = ?", (run_id,))
        return {r[0] for r in rows}

    def album_size(self, album: str) -> int:
        row = self.db.execute(
            "SELECT COUNT(*) FROM memberships WHERE album = ?", (album,)
        ).fetchone()
        return int(row[0])

    def forget_run(self, run_id: str, deleted_albums: Iterable[str]) -> None:
        """Drop everything a run recorded, after the writer has reverted it in Photos."""
        with self.transaction() as db:
            db.execute("DELETE FROM memberships WHERE run_id = ?", (run_id,))
            db.execute("DELETE FROM keywords WHERE run_id = ?", (run_id,))
            db.execute("DELETE FROM suggested_events WHERE run_id = ?", (run_id,))
            db.execute("DELETE FROM trips WHERE run_id = ?", (run_id,))
            db.execute("DELETE FROM processed WHERE first_run_id = ?", (run_id,))
            db.executemany("DELETE FROM albums WHERE name = ?", [(a,) for a in deleted_albums])
            db.execute(
                "UPDATE albums SET created_by_run = NULL WHERE created_by_run = ?", (run_id,)
            )
            db.execute(
                "UPDATE runs SET status = 'undone', high_water = NULL WHERE id = ?", (run_id,)
            )

    # Stats ---------------------------------------------------------------------------------
    def stats(self) -> dict[str, object]:
        def one(sql: str) -> int:
            return int(self.db.execute(sql).fetchone()[0])

        per_album = dict(
            self.db.execute(
                "SELECT album, COUNT(*) FROM memberships GROUP BY album ORDER BY album"
            ).fetchall()
        )
        return {
            "runs": one("SELECT COUNT(*) FROM runs"),
            "runs_ok": one("SELECT COUNT(*) FROM runs WHERE status = 'ok'"),
            "photos_processed": one("SELECT COUNT(*) FROM processed"),
            "memberships": one("SELECT COUNT(*) FROM memberships"),
            "albums": len(per_album),
            "trips": one("SELECT COUNT(*) FROM trips"),
            "suggested_events": one("SELECT COUNT(*) FROM suggested_events"),
            "per_album": per_album,
        }
