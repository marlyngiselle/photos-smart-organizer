"""Adapters tested against fakes. Nothing here opens a Photos library or talks to Photos.app."""

from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from photosorg.adapters.jxa_writer import OSASCRIPT, JxaPhotosWriter, WriterError, script_path
from photosorg.adapters.osxphotos_reader import OsxPhotosReader, ReaderUnavailable, to_photo
from photosorg.models import MediaType, Scores
from photosorg.ports import PhotoReader, PhotoWriter

T = datetime(2026, 5, 21, 18, 0, tzinfo=UTC)


def fake_info(uuid: str = "AAAA", **kw: Any) -> SimpleNamespace:
    base: dict[str, Any] = {
        "uuid": uuid,
        "date": T,
        "date_added": T,
        "location": (48.8584, 2.2945),
        "place": SimpleNamespace(names=SimpleNamespace(country=["France"], city=["Paris"])),
        "ismovie": False,
        "live_photo": False,
        "burst": False,
        "burst_key_photo": None,
        "burst_photos": [],
        "burst_selected": False,
        "duplicates": [],
        "score": SimpleNamespace(
            overall=0.4, curation=0.6, sharply_focused_subject=0.5, well_framed_subject=0.3
        ),
        "persons": ["Alex", "_UNKNOWN_"],
        "face_info": [object(), object()],
        "screenshot": False,
        "favorite": False,
        "hidden": False,
        "intrash": False,
    }
    base.update(kw)
    return SimpleNamespace(**base)


def test_to_photo_maps_every_field() -> None:
    p = to_photo(fake_info())
    assert (p.uuid, p.taken_at, p.country, p.city) == ("AAAA", T, "France", "Paris")
    assert (p.latitude, p.longitude) == (48.8584, 2.2945)
    assert (p.faces, p.persons) == (2, 1)  # unnamed faces are not people you know
    assert p.scores == Scores(0.4, 0.6, 0.5, 0.3)
    assert p.media_type is MediaType.PHOTO


def test_to_photo_handles_missing_place_and_location() -> None:
    p = to_photo(fake_info(location=(None, None), place=None))
    assert not p.has_location and p.country is None and p.city is None


def test_all_zero_scores_mean_not_analysed() -> None:
    zero = SimpleNamespace(
        overall=0.0, curation=0.0, sharply_focused_subject=0.0, well_framed_subject=0.0
    )
    assert to_photo(fake_info(score=zero)).scores == Scores()


def test_media_types() -> None:
    assert to_photo(fake_info(ismovie=True)).media_type is MediaType.VIDEO
    assert to_photo(fake_info(live_photo=True)).media_type is MediaType.LIVE


def test_burst_and_duplicate_groups() -> None:
    key = SimpleNamespace(uuid="KEY")
    p = to_photo(fake_info("B2", burst=True, burst_key_photo=key, burst_selected=True))
    assert p.burst_group == "KEY" and p.burst_pick
    q = to_photo(fake_info("B3", burst=True, burst_photos=[SimpleNamespace(uuid="B1")]))
    assert q.burst_group == "B1"
    d = to_photo(fake_info("D2", duplicates=[SimpleNamespace(uuid="D1")]))
    assert d.duplicate_group == "D1"


class FakeDB:
    def __init__(self, infos: list[SimpleNamespace]) -> None:
        self.infos = infos
        self.calls: list[dict[str, Any]] = []

    def photos(self, **kw: Any) -> list[SimpleNamespace]:
        self.calls.append(kw)
        return self.infos


def test_reader_filters_trash_and_uses_date_added_for_late_syncs() -> None:
    old = datetime(2026, 1, 1, tzinfo=UTC)
    db = FakeDB(
        [
            fake_info("NEW"),
            fake_info("TRASH", intrash=True),
            fake_info("OLD", date=old, date_added=old),
            fake_info("LATE", date=old, date_added=T),  # taken long ago, synced today
        ]
    )
    reader = OsxPhotosReader(db=db)
    assert isinstance(reader, PhotoReader)
    got = [p.uuid for p in reader.photos(since=datetime(2026, 5, 1, tzinfo=UTC))]
    assert got == ["NEW", "LATE"]
    assert [p.uuid for p in reader.photos(since=None)] == ["NEW", "OLD", "LATE"]


class FakeRunner:
    def __init__(self, reply: str = "") -> None:
        self.reply = reply
        self.argv: list[list[str]] = []

    def __call__(self, argv: list[str]) -> str:
        self.argv.append(argv)
        return self.reply


def test_writer_builds_osascript_calls() -> None:
    run = FakeRunner("created")
    w = JxaPhotosWriter(runner=run, script=Path("/x/photos_album.js"))
    assert isinstance(w, PhotoWriter)
    assert w.ensure_album("Smart Organizer", "Trip · Kyoto · 2026-06") is True
    w.add_to_album("Smart Organizer", "A", ["U1", "U2"])
    w.remove_from_album("Smart Organizer", "A", ["U1"])
    w.delete_album("Smart Organizer", "A")
    w.add_keyword(["U1"], "photosorg:suggested")
    w.remove_keyword(["U1"], "photosorg:suggested")
    head = [OSASCRIPT, "-l", "JavaScript", "/x/photos_album.js"]
    assert run.argv == [
        [*head, "ensure", "Smart Organizer", "Trip · Kyoto · 2026-06"],
        [*head, "add", "Smart Organizer", "A", "U1", "U2"],
        [*head, "remove", "Smart Organizer", "A", "U1"],
        [*head, "delete", "Smart Organizer", "A"],
        [*head, "kw-add", "photosorg:suggested", "U1"],
        [*head, "kw-remove", "photosorg:suggested", "U1"],
    ]


def test_writer_skips_empty_batches() -> None:
    run = FakeRunner()
    w = JxaPhotosWriter(runner=run, script=Path("/x.js"))
    w.add_to_album("F", "A", [])
    w.remove_from_album("F", "A", [])
    w.add_keyword([], "k")
    assert run.argv == []
    assert (
        JxaPhotosWriter(runner=FakeRunner("exists"), script=Path("/x.js")).ensure_album("F", "A")
        is False
    )


def test_writer_surfaces_osascript_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    from photosorg.adapters import jxa_writer

    def fail(*_: Any, **__: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], 1, "", "execution error: Not authorized (-1743)")

    monkeypatch.setattr(jxa_writer.subprocess, "run", fail)
    with pytest.raises(WriterError, match="-1743"):
        JxaPhotosWriter(script=Path("/x.js")).delete_album("F", "A")


def test_jxa_script_ships_with_the_package() -> None:
    path = script_path()
    text = path.read_text()
    assert path.name == "photos_album.js"
    assert "function run(argv)" in text
    # The bridge never touches photo content or favourites.
    for forbidden in ("favorite =", "favorite=", "export(", "import(", ".duplicate("):
        assert forbidden not in text


@pytest.mark.skipif(shutil.which("osacompile") is None, reason="macOS only")
def test_jxa_script_compiles(tmp_path: Path) -> None:
    out = tmp_path / "photos_album.scpt"
    proc = subprocess.run(
        ["osacompile", "-l", "JavaScript", "-o", str(out), str(script_path())],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert out.exists()


def test_reader_explains_a_blocked_library(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked(**_: object) -> None:
        try:
            raise PermissionError(1, "Operation not permitted")
        except PermissionError as exc:
            try:
                raise OSError("Error copying Photos.sqlite: Operation not permitted") from exc
            except OSError as inner:
                raise OSError("Error copying Photos.sqlite") from inner

    monkeypatch.setitem(sys.modules, "osxphotos", SimpleNamespace(PhotosDB=blocked))
    with pytest.raises(ReaderUnavailable, match="Full Disk Access"):
        list(OsxPhotosReader().photos(None))
