"""Deterministic album names.

The same photo and the same config always produce the same names, in the same order. That is
what makes a re-run a no-op instead of a pile of duplicate albums.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date

from photosorg.config import Config, Geofence, Templates
from photosorg.geo import matching_geofences
from photosorg.models import Photo

_SPACES = re.compile(r"\s+")
MAX_NAME = 120


def clean(name: str) -> str:
    """Normalise Unicode (NFC), collapse whitespace and drop characters Photos dislikes."""
    name = unicodedata.normalize("NFC", name)
    name = "".join(ch for ch in name if unicodedata.category(ch)[0] != "C")
    name = name.replace("/", "-").replace(":", "-")
    name = _SPACES.sub(" ", name).strip()
    return name[:MAX_NAME].rstrip()


def _label(value: str | None) -> str | None:
    if value is None:
        return None
    value = clean(value)
    return value or None


def year_album(t: Templates, day: date) -> str:
    return clean(t.year.format(year=day.year, month=day.month))


def month_album(t: Templates, day: date) -> str:
    return clean(t.month.format(year=day.year, month=day.month))


def trip_album(t: Templates, city: str, start: date) -> str:
    return clean(t.trip.format(city=city, year=start.year, month=start.month))


def place_albums(photo: Photo, cfg: Config) -> list[str]:
    rules, t = cfg.albums, cfg.albums.templates
    names: list[str] = []
    country, city = _label(photo.country), _label(photo.city)
    if rules.by_geofence and photo.latitude is not None and photo.longitude is not None:
        home = Geofence(cfg.home.name, cfg.home.lat, cfg.home.lon, cfg.home.radius_km * 1000)
        fences = (home, *cfg.geofences)
        names += [
            clean(t.geofence.format(name=f.name))
            for f in matching_geofences(photo.latitude, photo.longitude, fences)
        ]
    if rules.by_country and country:
        names.append(clean(t.country.format(country=country)))
    if rules.by_city and country and city:
        names.append(clean(t.city.format(country=country, city=city)))
    return names


def date_albums(photo: Photo, cfg: Config) -> list[str]:
    rules, t = cfg.albums, cfg.albums.templates
    names: list[str] = []
    if rules.by_year:
        names.append(year_album(t, photo.day))
    if rules.by_month:
        names.append(month_album(t, photo.day))
    return names


def albums_for(photo: Photo, cfg: Config) -> list[str]:
    """Place and date albums for one photo, de-duplicated, order preserved."""
    return list(dict.fromkeys(place_albums(photo, cfg) + date_albums(photo, cfg)))


def disambiguate(name: str, taken: set[str]) -> str:
    """``name`` if free, else ``name (2)``, ``name (3)``... The first free one wins."""
    if name not in taken:
        return name
    n = 2
    while f"{name} ({n})" in taken:
        n += 1
    return f"{name} ({n})"
