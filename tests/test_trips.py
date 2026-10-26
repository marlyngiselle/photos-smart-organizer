from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime

from photosorg import fixtures
from photosorg.config import Config, TripRules
from photosorg.fixtures import CEST, PDT, shot
from photosorg.models import Photo
from photosorg.planner import in_scope
from photosorg.trips import KnownTrip, detect, dominant_city


def test_demo_library_has_two_trips(cfg: Config, photos: list[Photo]) -> None:
    trips = detect([p for p in photos if in_scope(p, cfg)], cfg)  # the video is out of scope
    assert [(t.name, t.start, t.end, len(t.uuids)) for t in trips] == [
        ("Trip · Paris · 2026-05", date(2026, 5, 21), date(2026, 5, 24), 11),
        ("Trip · Kyoto · 2026-06", date(2026, 6, 3), date(2026, 6, 5), 6),
    ]


def test_day_out_closer_than_threshold_is_not_a_trip(cfg: Config, photos: list[Photo]) -> None:
    ggp = {fixtures.fake_uuid("ggp-meadow"), fixtures.fake_uuid("ggp-running")}
    assert not any(ggp & set(t.uuids) for t in detect(photos, cfg))


def test_dominant_city_wins_over_day_trip(cfg: Config, photos: list[Photo]) -> None:
    paris = detect(photos, cfg)[0]
    assert paris.city == "Paris"  # Versailles photos belong to the Paris trip


def test_too_few_photos_is_not_a_trip(cfg: Config) -> None:
    few = [shot(f"p{i}", datetime(2026, 5, 21, 10, i, tzinfo=CEST), "louvre") for i in range(4)]
    assert detect(few, cfg) == []
    assert len(detect(few, replace(cfg, trips=TripRules(min_photos=4)))) == 1


def test_gap_longer_than_allowed_splits_trips(cfg: Config) -> None:
    a = [shot(f"a{i}", datetime(2026, 5, 1, 10, i, tzinfo=CEST), "louvre") for i in range(5)]
    b = [shot(f"b{i}", datetime(2026, 5, 4, 10, i, tzinfo=CEST), "louvre") for i in range(5)]
    names = [t.name for t in detect(a + b, cfg)]
    assert names == ["Trip · Paris · 2026-05", "Trip · Paris · 2026-05 (2)"]


def test_one_quiet_day_does_not_split(cfg: Config) -> None:
    a = [shot(f"a{i}", datetime(2026, 5, 1, 10, i, tzinfo=CEST), "louvre") for i in range(5)]
    b = [shot(f"b{i}", datetime(2026, 5, 3, 10, i, tzinfo=CEST), "louvre") for i in range(5)]
    assert len(detect(a + b, cfg)) == 1


def test_a_day_at_home_splits_trips(cfg: Config) -> None:
    a = [shot(f"a{i}", datetime(2026, 5, 1, 10, i, tzinfo=CEST), "louvre") for i in range(5)]
    home = [shot("home", datetime(2026, 5, 2, 10, 0, tzinfo=PDT), "apple_park")]
    b = [shot(f"b{i}", datetime(2026, 5, 3, 10, i, tzinfo=CEST), "louvre") for i in range(5)]
    assert len(detect(a + home + b, cfg)) == 2


def test_known_trip_keeps_its_name_when_extended(cfg: Config) -> None:
    known = [KnownTrip("Trip · Paris · 2026-05", date(2026, 5, 21), date(2026, 5, 24), "Paris")]
    # Two late photos from the day after, in Versailles; below min_photos on their own.
    late = [
        shot(f"v{i}", datetime(2026, 5, 25, 10, i, tzinfo=CEST), "versailles") for i in range(2)
    ]
    [trip] = detect(late, cfg, known)
    assert trip.name == "Trip · Paris · 2026-05"
    assert (trip.start, trip.end) == (date(2026, 5, 21), date(2026, 5, 25))


def test_new_trip_avoids_known_names(cfg: Config) -> None:
    known = [KnownTrip("Trip · Paris · 2026-05", date(2026, 5, 1), date(2026, 5, 2), "Paris")]
    later = [shot(f"x{i}", datetime(2026, 5, 20, 10, i, tzinfo=CEST), "louvre") for i in range(5)]
    assert detect(later, cfg, known)[0].name == "Trip · Paris · 2026-05 (2)"


def test_trips_can_be_disabled(cfg: Config, photos: list[Photo]) -> None:
    off = replace(cfg, albums=replace(cfg.albums, trips=False))
    assert detect(photos, off) == []


def test_dominant_city_tie_break_and_fallbacks() -> None:
    t = datetime(2026, 5, 1, tzinfo=CEST)
    tie = [shot("a", t, "versailles"), shot("b", t, "louvre")]
    assert dominant_city(tie) == "Paris"  # alphabetical on a tie
    nameless = [Photo(uuid="x", taken_at=t, latitude=1, longitude=1, country="France")]
    assert dominant_city(nameless) == "France"
    assert dominant_city([Photo(uuid="y", taken_at=t, latitude=1, longitude=1)]) == "Somewhere"
