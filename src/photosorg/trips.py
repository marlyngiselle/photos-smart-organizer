"""Trip detection: consecutive days far from home become one ``Trip · City · YYYY-MM`` album.

Trips are sticky. Once a trip has a name (recorded in the state DB), later photos that extend it
keep that name, even if they shift which city has the most photos.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date

from photosorg.config import Config
from photosorg.geo import haversine_m
from photosorg.models import Photo, Trip
from photosorg.naming import disambiguate, trip_album


@dataclass(frozen=True, slots=True)
class KnownTrip:
    name: str
    start: date
    end: date
    city: str


def is_home(photo: Photo, cfg: Config) -> bool:
    if photo.latitude is None or photo.longitude is None:
        return False
    d = haversine_m(photo.latitude, photo.longitude, cfg.home.lat, cfg.home.lon)
    return d <= cfg.home.radius_km * 1000


def is_away(photo: Photo, cfg: Config) -> bool:
    if photo.latitude is None or photo.longitude is None:
        return False
    d = haversine_m(photo.latitude, photo.longitude, cfg.home.lat, cfg.home.lon)
    return d > cfg.trips.min_distance_km * 1000


def dominant_city(photos: Iterable[Photo]) -> str:
    cities = Counter(p.city for p in photos if p.city)
    if not cities:
        cities = Counter(p.country for p in photos if p.country)
    if not cities:
        return "Somewhere"
    best = max(cities.values())
    return sorted(c for c, n in cities.items() if n == best)[0]


def _clusters(photos: Sequence[Photo], cfg: Config) -> list[list[Photo]]:
    away = sorted((p for p in photos if is_away(p, cfg)), key=lambda p: (p.taken_at, p.uuid))
    home_days = {p.day for p in photos if is_home(p, cfg)}
    clusters: list[list[Photo]] = []
    for p in away:
        if clusters:
            prev = clusters[-1][-1].day
            gap = (p.day - prev).days - 1
            interrupted = any(prev < h < p.day for h in home_days)
            if gap <= cfg.trips.max_gap_days and not interrupted:
                clusters[-1].append(p)
                continue
        clusters.append([p])
    return clusters


def _touches(start: date, end: date, known: KnownTrip, max_gap: int) -> bool:
    if start > known.end:
        return (start - known.end).days - 1 <= max_gap
    if end < known.start:
        return (known.start - end).days - 1 <= max_gap
    return True  # overlap


def detect(photos: Sequence[Photo], cfg: Config, known: Sequence[KnownTrip] = ()) -> list[Trip]:
    """Cluster away-from-home photos into trips, reusing names of trips seen in earlier runs."""
    if not cfg.albums.trips:
        return []
    taken = {k.name for k in known}
    trips: list[Trip] = []
    for cluster in _clusters(photos, cfg):
        start, end = cluster[0].day, cluster[-1].day
        uuids = tuple(p.uuid for p in cluster)
        match = next(
            (
                k
                for k in sorted(known, key=lambda k: k.start)
                if _touches(start, end, k, cfg.trips.max_gap_days)
            ),
            None,
        )
        if match is not None:
            trips.append(
                Trip(match.name, min(start, match.start), max(end, match.end), match.city, uuids)
            )
            continue
        if len(cluster) < cfg.trips.min_photos:
            continue
        city = dominant_city(cluster)
        name = disambiguate(trip_album(cfg.albums.templates, city, start), taken)
        taken.add(name)
        trips.append(Trip(name, start, end, city, uuids))
    return trips
