"""Great-circle distance and geofence matching."""

from __future__ import annotations

from collections.abc import Iterable
from math import asin, cos, radians, sin, sqrt

from photosorg.config import Geofence

EARTH_RADIUS_M = 6_371_008.8  # IUGG mean radius


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance in metres between two WGS84 points."""
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = phi2 - phi1
    dlmb = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_M * asin(min(1.0, sqrt(a)))


def matching_geofences(lat: float, lon: float, fences: Iterable[Geofence]) -> list[Geofence]:
    """Every geofence that contains the point, nearest centre first, then by name."""
    hits = [(haversine_m(lat, lon, f.lat, f.lon), f.name, f) for f in fences]
    return [f for d, _, f in sorted(hits, key=lambda h: (h[0], h[1])) if d <= f.radius_m]
