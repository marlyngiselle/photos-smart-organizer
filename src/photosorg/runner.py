"""Glue between planner, state and writer: run, plan and undo."""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from photosorg.config import Config
from photosorg.models import Membership, Plan
from photosorg.planner import StateView, build_plan
from photosorg.ports import PhotoReader, PhotoWriter
from photosorg.state import StateStore, new_run_id

log = logging.getLogger("photosorg")
CHUNK = 200


class UndoError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class RunResult:
    run_id: str | None
    plan: Plan
    added: int
    albums_created: int
    dry_run: bool


def resolve_since(since: str, state: StateStore, cfg: Config) -> datetime | None:
    """``auto`` means the last good run's high-water mark minus the trip lookback window."""
    if since == "auto":
        hw = state.high_water()
        return None if hw is None else hw - timedelta(days=cfg.trips.lookback_days)
    if since == "all":
        return None
    parsed = datetime.fromisoformat(since)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def snapshot(state: StateStore) -> StateView:
    return StateView(
        frozenset(state.memberships()),
        tuple(state.known_trips()),
        frozenset(state.suggested_events()),
    )


def make_plan(
    reader: PhotoReader, state: StateStore, cfg: Config, since: str, now: datetime
) -> Plan:
    photos = list(reader.photos(resolve_since(since, state, cfg)))
    return build_plan(photos, cfg, snapshot(state), now)


def run(
    reader: PhotoReader,
    writer: PhotoWriter,
    state: StateStore,
    cfg: Config,
    *,
    since: str = "auto",
    dry_run: bool = False,
    now: datetime | None = None,
) -> RunResult:
    now = now or datetime.now(UTC)
    plan = make_plan(reader, state, cfg, since, now)
    if dry_run:
        return RunResult(None, plan, 0, 0, True)

    run_id = new_run_id(now)
    state.start_run(run_id, now)
    added = created = 0
    try:
        known = state.known_albums()
        for album, uuids in plan.albums().items():
            was_created = writer.ensure_album(cfg.folder, album)
            if was_created:
                created += 1
            if album not in known:
                state.record_album(album, run_id if was_created else None)
            missing: list[str] = []
            for i in range(0, len(uuids), CHUNK):
                chunk = uuids[i : i + CHUNK]
                gone = set(writer.add_to_album(cfg.folder, album, chunk))
                missing.extend(u for u in chunk if u in gone)
                placed = (Membership(album, u) for u in chunk if u not in gone)
                added += state.record_memberships(run_id, placed)
            log.info("album %r: +%d", album, len(uuids) - len(missing))
            if missing:
                log.warning(
                    "album %r: %d photos not reachable in Photos, skipped: %s",
                    album,
                    len(missing),
                    ", ".join(missing[:5]) + (" ..." if len(missing) > 5 else ""),
                )

        fav = cfg.favourites
        suggested = [sp.photo.uuid for sp in plan.suggestions]
        if fav.enabled and fav.add_keyword and suggested:
            writer.add_keyword(suggested, fav.keyword)
            state.record_keywords(run_id, suggested, fav.keyword)
        for t in plan.trips:
            state.upsert_trip(run_id, t.name, t.start, t.end, t.city)
        state.record_suggested_events(run_id, plan.settled_events)
        state.record_processed(run_id, plan.seen)
        state.finish_run(run_id, "ok", plan.latest or now, added)
    except Exception:
        state.finish_run(run_id, "failed", None, added)
        log.exception(
            "run %s failed after %d additions; they are recorded and undoable", run_id, added
        )
        raise
    return RunResult(run_id, plan, added, created, False)


@dataclass(frozen=True, slots=True)
class UndoResult:
    run_id: str
    removed: int
    albums_deleted: list[str]
    keywords_removed: int


def undo(
    run_id: str, writer: PhotoWriter, state: StateStore, cfg: Config, *, dry_run: bool = False
) -> UndoResult:
    record = state.get_run(run_id)
    if record is None:
        raise UndoError(f"unknown run id: {run_id}")
    if record.status == "undone":
        raise UndoError(f"run {run_id} was already undone")

    by_album: dict[str, list[str]] = defaultdict(list)
    for m in state.run_memberships(run_id):
        by_album[m.album].append(m.uuid)
    keywords = state.run_keywords(run_id)
    created = state.albums_created_by(run_id)
    empty_after = sorted(a for a in created if state.album_size(a) == len(by_album.get(a, [])))
    removed = sum(len(v) for v in by_album.values())
    kw_removed = sum(len(v) for v in keywords.values())
    if dry_run:
        return UndoResult(run_id, removed, empty_after, kw_removed)

    for album in sorted(by_album):
        if album in empty_after:
            continue  # deleting the album removes the memberships in one step
        uuids = by_album[album]
        for i in range(0, len(uuids), CHUNK):
            writer.remove_from_album(cfg.folder, album, uuids[i : i + CHUNK])
    for album in empty_after:
        writer.delete_album(cfg.folder, album)
    for kw, uuids in keywords.items():
        writer.remove_keyword(uuids, kw)
    state.forget_run(run_id, empty_after)
    return UndoResult(run_id, removed, empty_after, kw_removed)
