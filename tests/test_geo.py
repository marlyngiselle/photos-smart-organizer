from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from photosorg.config import Geofence
from photosorg.geo import haversine_m, matching_geofences

lat = st.floats(min_value=-90, max_value=90, allow_nan=False)
lon = st.floats(min_value=-180, max_value=180, allow_nan=False)


def test_known_distance_paris_london() -> None:
    # Notre-Dame de Paris to Big Ben is roughly 340 km as the crow flies.
    d = haversine_m(48.8530, 2.3499, 51.5007, -0.1246)
    assert 335_000 < d < 345_000


def test_known_distance_eiffel_to_louvre() -> None:
    assert haversine_m(48.8584, 2.2945, 48.8606, 2.3376) == pytest.approx(3_160, rel=0.02)


def test_same_point_is_zero() -> None:
    assert haversine_m(35.0394, 135.7292, 35.0394, 135.7292) == 0


def test_antipodes_is_half_circumference() -> None:
    assert haversine_m(0, 0, 0, 180) == pytest.approx(20_015_115, rel=1e-4)


@given(lat, lon, lat, lon)
def test_symmetric_and_non_negative(a: float, b: float, c: float, d: float) -> None:
    ab = haversine_m(a, b, c, d)
    assert ab >= 0
    assert ab == pytest.approx(haversine_m(c, d, a, b), abs=1e-6)


@given(lat, lon, lat, lon, lat, lon)
def test_triangle_inequality(a: float, b: float, c: float, d: float, e: float, f: float) -> None:
    assert haversine_m(a, b, e, f) <= haversine_m(a, b, c, d) + haversine_m(c, d, e, f) + 1e-3


def test_geofence_inside_and_outside() -> None:
    park = Geofence("Golden Gate Park", 37.7694, -122.4862, 1200)
    assert matching_geofences(37.7700, -122.4800, [park]) == [park]
    assert matching_geofences(37.8199, -122.4783, [park]) == []  # the bridge, 5.6 km away


def test_geofence_order_is_nearest_first_then_name() -> None:
    a = Geofence("B wide", 48.8584, 2.2945, 5_000)
    b = Geofence("A tight", 48.8584, 2.2945, 500)
    c = Geofence("Louvre", 48.8606, 2.3376, 5_000)
    hits = matching_geofences(48.8585, 2.2946, [c, a, b])
    assert [h.name for h in hits] == ["A tight", "B wide", "Louvre"]
