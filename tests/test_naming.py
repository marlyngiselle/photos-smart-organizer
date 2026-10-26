from __future__ import annotations

from dataclasses import replace
from datetime import date

from conftest import by_label
from photosorg.config import AlbumRules, Config, Templates
from photosorg.models import Photo
from photosorg.naming import albums_for, clean, disambiguate, month_album, trip_album


def test_place_and_date_albums_for_a_paris_photo(cfg: Config, photos: list[Photo]) -> None:
    p = by_label(photos, "louvre-pyramid")
    assert albums_for(p, cfg) == [
        "Places · France",
        "Places · France · Paris",
        "Timeline · 2026",
        "Timeline · 2026-05",
    ]


def test_home_and_custom_geofences_come_first(cfg: Config, photos: list[Photo]) -> None:
    assert albums_for(by_label(photos, "home-bbq"), cfg)[0] == "Places · Home"
    assert albums_for(by_label(photos, "ggp-meadow"), cfg)[0] == "Places · Golden Gate Park"


def test_photo_without_location_gets_date_albums_only(cfg: Config, photos: list[Photo]) -> None:
    assert albums_for(by_label(photos, "scanned-print"), cfg) == [
        "Timeline · 2026",
        "Timeline · 2026-06",
    ]


def test_rules_can_be_switched_off(cfg: Config, photos: list[Photo]) -> None:
    off = replace(cfg, albums=AlbumRules(by_country=False, by_year=False, by_geofence=False))
    assert albums_for(by_label(photos, "louvre-pyramid"), off) == [
        "Places · France · Paris",
        "Timeline · 2026-05",
    ]


def test_custom_templates() -> None:
    t = Templates(month="{year}/{month:02d}", trip="{city} {year}")
    assert month_album(t, date(2026, 3, 1)) == "2026-03"  # "/" is not allowed in names
    assert trip_album(t, "Kyoto", date(2026, 6, 3)) == "Kyoto 2026"


def test_clean_normalises_unicode_and_whitespace() -> None:
    decomposed = "Montréal"  # e + combining acute
    assert clean(f"  Places ·  {decomposed}\n") == "Places · Montréal"
    assert clean("a:b/c") == "a-b-c"
    assert len(clean("x" * 500)) == 120


def test_naming_is_deterministic(cfg: Config, photos: list[Photo]) -> None:
    first = [albums_for(p, cfg) for p in photos]
    assert first == [albums_for(p, cfg) for p in reversed(photos)][::-1]


def test_disambiguate() -> None:
    assert disambiguate("Trip · Paris · 2026-05", set()) == "Trip · Paris · 2026-05"
    taken = {"Trip · Paris · 2026-05", "Trip · Paris · 2026-05 (2)"}
    assert disambiguate("Trip · Paris · 2026-05", taken) == "Trip · Paris · 2026-05 (3)"
