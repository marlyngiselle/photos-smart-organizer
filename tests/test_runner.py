from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from photosorg import runner
from photosorg.adapters.memory import MemoryReader, MemoryWriter
from photosorg.config import Config
from photosorg.fixtures import CEST, PDT, fake_uuid, shot
from photosorg.models import Photo
from photosorg.planner import StateView, build_plan, is_settled
from photosorg.state import StateStore


def test_first_run_files_everything(
    reader: MemoryReader, writer: MemoryWriter, state: StateStore, cfg: Config, now: datetime
) -> None:
    res = runner.run(reader, writer, state, cfg, now=now)
    assert res.added == len(res.plan.to_add) > 0
    assert res.albums_created == len(writer.albums) == 16
    assert all(folder == "Smart Organizer" for folder, _ in writer.albums)
    assert state.get_run(res.run_id or "").status == "ok"  # type: ignore[union-attr]


def test_second_run_is_a_no_op(
    reader: MemoryReader, writer: MemoryWriter, state: StateStore, cfg: Config, now: datetime
) -> None:
    first = runner.run(reader, writer, state, cfg, since="all", now=now)
    calls = len(writer.calls)
    second = runner.run(reader, writer, state, cfg, since="all", now=now)
    assert second.added == 0
    assert second.plan.to_add == []
    # Suggestions of settled days are not re-derived, so they are not counted again.
    assert second.plan.already_present == first.added - len(first.plan.suggestions)
    assert len(writer.calls) == calls  # not even an ensure_album


def test_dry_run_changes_nothing(
    reader: MemoryReader, writer: MemoryWriter, state: StateStore, cfg: Config, now: datetime
) -> None:
    res = runner.run(reader, writer, state, cfg, dry_run=True, now=now)
    assert res.run_id is None and res.plan.to_add
    assert writer.calls == [] and state.runs() == []


def test_today_is_suggested_only_once_the_day_is_over(
    reader: MemoryReader, writer: MemoryWriter, state: StateStore, cfg: Config, now: datetime
) -> None:
    coffee = fake_uuid("today-coffee")
    first = runner.run(reader, writer, state, cfg, now=now)
    assert coffee not in {sp.photo.uuid for sp in first.plan.suggestions}
    later = runner.run(reader, writer, state, cfg, since="all", now=now + timedelta(days=1))
    assert [sp.photo.uuid for sp in later.plan.suggestions] == [coffee]
    assert later.plan.settled_events == ["day:2026-06-20"]


def test_settled_events_are_not_re_judged(
    reader: MemoryReader, writer: MemoryWriter, state: StateStore, cfg: Config, now: datetime
) -> None:
    runner.run(reader, writer, state, cfg, now=now)
    # A stronger photo of an old, already judged day syncs late: it is filed, not suggested.
    late = shot(
        "late-sync",
        datetime(2026, 5, 2, 12, 0, tzinfo=PDT),
        "apple_park",
        overall=1.0,
        curation=1.0,
        sharpness=1.0,
        composition=1.0,
        faces=3,
        persons=3,
    )
    res = runner.run(MemoryReader([late]), writer, state, cfg, since="all", now=now)
    assert res.plan.suggestions == []
    assert ("Smart Organizer", "Timeline · 2026-05") in writer.albums
    assert late.uuid in writer.albums[("Smart Organizer", "Timeline · 2026-05")]


def test_trip_extension_across_runs_keeps_the_album(
    writer: MemoryWriter, state: StateStore, cfg: Config, photos: list[Photo], now: datetime
) -> None:
    runner.run(MemoryReader(photos), writer, state, cfg, now=now)
    extra = shot("paris-extra-day", datetime(2026, 5, 25, 10, 0, tzinfo=CEST), "louvre")
    res = runner.run(MemoryReader([extra]), writer, state, cfg, since="all", now=now)
    assert [t.name for t in res.plan.trips] == ["Trip · Paris · 2026-05"]
    assert extra.uuid in writer.albums[("Smart Organizer", "Trip · Paris · 2026-05")]


def test_undo_restores_the_previous_state(
    reader: MemoryReader, writer: MemoryWriter, state: StateStore, cfg: Config, now: datetime
) -> None:
    res = runner.run(reader, writer, state, cfg, now=now)
    undo = runner.undo(res.run_id or "", writer, state, cfg)
    assert undo.removed == res.added
    assert writer.albums == {}  # every album was created by that run, so each is deleted
    assert state.memberships() == set()
    assert state.get_run(res.run_id or "").status == "undone"  # type: ignore[union-attr]
    # and the next run files everything again
    again = runner.run(reader, writer, state, cfg, since="all", now=now)
    assert again.added == res.added


def test_undo_of_a_later_run_keeps_albums_that_existed(
    writer: MemoryWriter, state: StateStore, cfg: Config, photos: list[Photo], now: datetime
) -> None:
    first = runner.run(MemoryReader(photos[:3]), writer, state, cfg, now=now)
    second = runner.run(MemoryReader(photos[3:4]), writer, state, cfg, since="all", now=now)
    runner.undo(second.run_id or "", writer, state, cfg)
    home = writer.albums[("Smart Organizer", "Places · Home")]
    assert photos[3].uuid not in home
    assert len(state.memberships()) == first.added


def test_undo_never_deletes_photos(
    reader: MemoryReader, writer: MemoryWriter, state: StateStore, cfg: Config, now: datetime
) -> None:
    res = runner.run(reader, writer, state, cfg, now=now)
    runner.undo(res.run_id or "", writer, state, cfg)
    verbs = {c[0] for c in writer.calls}
    assert verbs <= {"ensure", "add", "remove", "delete", "kw-add", "kw-remove"}
    assert all(c[0] != "delete" or len(c) == 3 for c in writer.calls)  # folder, album only


def test_undo_twice_and_unknown_runs_fail(
    reader: MemoryReader, writer: MemoryWriter, state: StateStore, cfg: Config, now: datetime
) -> None:
    res = runner.run(reader, writer, state, cfg, now=now)
    runner.undo(res.run_id or "", writer, state, cfg)
    with pytest.raises(runner.UndoError, match="already undone"):
        runner.undo(res.run_id or "", writer, state, cfg)
    with pytest.raises(runner.UndoError, match="unknown run"):
        runner.undo("nope", writer, state, cfg)


def test_undo_dry_run(
    reader: MemoryReader, writer: MemoryWriter, state: StateStore, cfg: Config, now: datetime
) -> None:
    res = runner.run(reader, writer, state, cfg, now=now)
    calls = len(writer.calls)
    preview = runner.undo(res.run_id or "", writer, state, cfg, dry_run=True)
    assert preview.removed == res.added and len(writer.calls) == calls


def test_keyword_is_opt_in_and_undone(
    reader: MemoryReader, writer: MemoryWriter, state: StateStore, cfg: Config, now: datetime
) -> None:
    on = replace(cfg, favourites=replace(cfg.favourites, add_keyword=True))
    res = runner.run(reader, writer, state, on, now=now)
    tagged = {u for u, kws in writer.keywords.items() if "photosorg:suggested" in kws}
    assert tagged == {sp.photo.uuid for sp in res.plan.suggestions}
    runner.undo(res.run_id or "", writer, state, on)
    assert not any(writer.keywords.values())

    off_writer = MemoryWriter()
    runner.run(reader, off_writer, StateStore(), cfg, now=now)
    assert off_writer.keywords == {}


def test_failure_mid_run_is_recorded_and_undoable(
    reader: MemoryReader, state: StateStore, cfg: Config, now: datetime
) -> None:
    flaky = MemoryWriter()
    calls = {"n": 0}
    original = flaky.add_to_album

    def add(folder: str, album: str, uuids: object) -> None:
        calls["n"] += 1
        if calls["n"] == 4:
            raise RuntimeError("Photos quit")
        original(folder, album, uuids)  # type: ignore[arg-type]

    flaky.add_to_album = add  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="Photos quit"):
        runner.run(reader, flaky, state, cfg, now=now)
    [record] = state.runs()
    assert record.status == "failed" and record.added > 0
    assert state.high_water() is None  # a failed run never moves the high-water mark
    runner.undo(record.id, flaky, state, cfg)
    assert state.memberships() == set()


def test_since_auto_uses_high_water_minus_lookback(
    reader: MemoryReader, writer: MemoryWriter, state: StateStore, cfg: Config, now: datetime
) -> None:
    assert runner.resolve_since("auto", state, cfg) is None
    runner.run(reader, writer, state, cfg, now=now)
    since = runner.resolve_since("auto", state, cfg)
    assert since == datetime(2026, 6, 20, 9, 0, tzinfo=PDT) - timedelta(days=14)
    assert runner.resolve_since("all", state, cfg) is None
    assert runner.resolve_since("2026-01-01", state, cfg).year == 2026  # type: ignore[union-attr]


def test_plan_is_pure(photos: list[Photo], cfg: Config, now: datetime) -> None:
    a = build_plan(photos, cfg, StateView(), now)
    b = build_plan(list(reversed(photos)), cfg, StateView(), now)
    assert a.to_add == b.to_add
    assert [s.photo.uuid for s in a.suggestions] == [s.photo.uuid for s in b.suggestions]


def test_group_by_event_judges_a_trip_as_one(
    photos: list[Photo], cfg: Config, now: datetime
) -> None:
    per_event = replace(cfg, favourites=replace(cfg.favourites, group_by="event"))
    plan = build_plan(photos, per_event, StateView(), now)
    assert "trip:Trip · Paris · 2026-05" in plan.settled_events
    paris = [s for s in plan.suggestions if s.photo.city in {"Paris", "Versailles"}]
    assert len(paris) == 2


def test_is_settled_boundary() -> None:
    p = shot("x", datetime(2026, 6, 1, 23, 59, tzinfo=PDT))
    assert not is_settled([p], datetime(2026, 6, 2, 5, 59, tzinfo=PDT), 6)
    assert is_settled([p], datetime(2026, 6, 2, 6, 0, tzinfo=PDT), 6)
