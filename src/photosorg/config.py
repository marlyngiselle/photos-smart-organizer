"""TOML configuration, parsed into frozen dataclasses with validated defaults."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, fields, replace
from pathlib import Path
from typing import Any

from photosorg.models import MediaType

DEFAULT_CONFIG_PATH = Path("~/.config/photosorg/config.toml").expanduser()


class ConfigError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Geofence:
    name: str
    lat: float
    lon: float
    radius_m: float


@dataclass(frozen=True, slots=True)
class Templates:
    country: str = "Places · {country}"
    city: str = "Places · {country} · {city}"
    geofence: str = "Places · {name}"
    year: str = "Timeline · {year}"
    month: str = "Timeline · {year}-{month:02d}"
    trip: str = "Trip · {city} · {year}-{month:02d}"


@dataclass(frozen=True, slots=True)
class AlbumRules:
    by_country: bool = True
    by_city: bool = True
    by_geofence: bool = True
    by_year: bool = True
    by_month: bool = True
    trips: bool = True
    templates: Templates = field(default_factory=Templates)


@dataclass(frozen=True, slots=True)
class Home:
    name: str = "Home"
    # Placeholder: Apple Park, a public landmark. Replace with your own in config.toml.
    lat: float = 37.3349
    lon: float = -122.0090
    radius_km: float = 25.0


@dataclass(frozen=True, slots=True)
class TripRules:
    min_distance_km: float = 100.0
    max_gap_days: int = 1
    min_photos: int = 5
    lookback_days: int = 14


@dataclass(frozen=True, slots=True)
class Weights:
    aesthetic: float = 0.35
    curation: float = 0.20
    sharpness: float = 0.15
    composition: float = 0.10
    faces: float = 0.10
    people: float = 0.10


@dataclass(frozen=True, slots=True)
class Penalties:
    blurry: float = 0.30
    blurry_threshold: float = 0.25
    unanalysed: float = 0.05


@dataclass(frozen=True, slots=True)
class FavouriteRules:
    enabled: bool = True
    album: str = "Suggested favourites"
    add_keyword: bool = False
    keyword: str = "photosorg:suggested"
    top_n_per_event: int = 2
    group_by: str = "day"
    min_score: float = 0.65
    near_duplicate_seconds: float = 3.0
    near_duplicate_score_delta: float = 0.08
    skip_existing_favourites: bool = True
    settle_hours: int = 6
    weights: Weights = field(default_factory=Weights)
    penalties: Penalties = field(default_factory=Penalties)


@dataclass(frozen=True, slots=True)
class Config:
    folder: str = "Smart Organizer"
    library: str | None = None
    media: tuple[MediaType, ...] = (MediaType.PHOTO, MediaType.LIVE)
    interval_minutes: int = 30
    albums: AlbumRules = field(default_factory=AlbumRules)
    home: Home = field(default_factory=Home)
    geofences: tuple[Geofence, ...] = ()
    trips: TripRules = field(default_factory=TripRules)
    favourites: FavouriteRules = field(default_factory=FavouriteRules)


def _merge(cls_instance: Any, section: dict[str, Any], where: str) -> Any:
    """Overlay a TOML table on a dataclass instance, rejecting unknown keys."""
    known = {f.name: f for f in fields(cls_instance)}
    updates: dict[str, Any] = {}
    for key, value in section.items():
        if key not in known:
            raise ConfigError(f"unknown key '{where}.{key}'")
        current = getattr(cls_instance, key)
        if isinstance(value, dict):
            updates[key] = _merge(current, value, f"{where}.{key}")
        elif isinstance(current, bool) and not isinstance(value, bool):
            raise ConfigError(f"'{where}.{key}' must be true or false")
        elif isinstance(current, float) and isinstance(value, int | float):
            updates[key] = float(value)
        else:
            updates[key] = value
    return replace(cls_instance, **updates)


def parse(data: dict[str, Any]) -> Config:
    cfg = Config()
    data = dict(data)
    library = data.pop("library", {})
    schedule = data.pop("schedule", {})
    raw_fences = data.pop("geofences", [])
    updates: dict[str, Any] = {}
    if "folder" in library:
        updates["folder"] = str(library["folder"])
    if "path" in library:
        updates["library"] = str(library["path"])
    if "media" in library:
        try:
            updates["media"] = tuple(MediaType(m) for m in library["media"])
        except ValueError as exc:
            raise ConfigError(f"library.media: {exc}") from exc
    if "interval_minutes" in schedule:
        updates["interval_minutes"] = int(schedule["interval_minutes"])
    cfg = replace(cfg, **updates)
    fences = []
    for i, f in enumerate(raw_fences):
        try:
            fences.append(
                Geofence(
                    str(f["name"]), float(f["lat"]), float(f["lon"]), float(f.get("radius_m", 300))
                )
            )
        except KeyError as exc:
            raise ConfigError(f"geofences[{i}] is missing {exc}") from exc
    cfg = replace(cfg, geofences=tuple(fences))
    merged: Config = _merge(cfg, data, "config")
    validate(merged)
    return merged


def validate(cfg: Config) -> None:
    if not cfg.folder.strip():
        raise ConfigError("library.folder must not be empty")
    if not 5 <= cfg.interval_minutes <= 1440:
        raise ConfigError("schedule.interval_minutes must be between 5 and 1440")
    for fence in cfg.geofences:
        if not (-90 <= fence.lat <= 90 and -180 <= fence.lon <= 180):
            raise ConfigError(f"geofence '{fence.name}' has invalid coordinates")
        if fence.radius_m <= 0:
            raise ConfigError(f"geofence '{fence.name}' needs a positive radius_m")
    if cfg.favourites.top_n_per_event < 1:
        raise ConfigError("favourites.top_n_per_event must be at least 1")
    if cfg.favourites.group_by not in ("day", "event"):
        raise ConfigError("favourites.group_by must be 'day' or 'event'")
    if not 0 <= cfg.favourites.min_score <= 1:
        raise ConfigError("favourites.min_score must be between 0 and 1")
    w = cfg.favourites.weights
    total = w.aesthetic + w.curation + w.sharpness + w.composition + w.faces + w.people
    if abs(total - 1.0) > 1e-6:
        raise ConfigError(f"favourites.weights must add up to 1.0 (got {total:.3f})")


def load(path: Path | None = None) -> Config:
    """Load ``path`` or the default location. A missing default file means defaults."""
    target = path or DEFAULT_CONFIG_PATH
    if not target.exists():
        if path is not None:
            raise ConfigError(f"config file not found: {target}")
        return Config()
    with target.open("rb") as fh:
        try:
            return parse(tomllib.load(fh))
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(f"{target}: {exc}") from exc
