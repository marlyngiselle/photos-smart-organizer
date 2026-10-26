"""A synthetic photo library for ``--demo`` and the test suite.

Every coordinate is a public landmark. No real photo, person or home address is involved.
Home is the default placeholder (Apple Park, Cupertino).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from photosorg.config import Config, Geofence
from photosorg.models import MediaType, Photo, Scores

_NS = uuid.UUID("6f1d6f5e-3c55-4a8e-9a43-1b0d1c0ffee0")

PDT = timezone(timedelta(hours=-7))
CEST = timezone(timedelta(hours=2))
JST = timezone(timedelta(hours=9))

DEMO_NOW = datetime(2026, 6, 20, 12, 0, tzinfo=PDT)

PLACES: dict[str, tuple[float, float, str, str]] = {
    "apple_park": (37.3349, -122.0090, "United States", "Cupertino"),
    "golden_gate_park": (37.7694, -122.4862, "United States", "San Francisco"),
    "eiffel_tower": (48.8584, 2.2945, "France", "Paris"),
    "louvre": (48.8606, 2.3376, "France", "Paris"),
    "versailles": (48.8049, 2.1204, "France", "Versailles"),
    "fushimi_inari": (34.9671, 135.7727, "Japan", "Kyoto"),
    "kinkaku_ji": (35.0394, 135.7292, "Japan", "Kyoto"),
}


def fake_uuid(label: str) -> str:
    return str(uuid.uuid5(_NS, label)).upper()


def shot(
    label: str,
    when: datetime,
    place: str | None = None,
    *,
    overall: float | None = 0.3,
    curation: float | None = 0.5,
    sharpness: float | None = 0.4,
    composition: float | None = 0.3,
    faces: int = 0,
    persons: int = 0,
    **extra: object,
) -> Photo:
    lat = lon = None
    country = city = None
    if place is not None:
        lat, lon, country, city = PLACES[place]
    return Photo(
        uuid=fake_uuid(label),
        taken_at=when,
        latitude=lat,
        longitude=lon,
        country=country,
        city=city,
        faces=faces,
        persons=persons,
        scores=Scores(overall, curation, sharpness, composition),
        **extra,  # type: ignore[arg-type]
    )


def demo_config() -> Config:
    return Config(geofences=(Geofence("Golden Gate Park", 37.7694, -122.4862, 1200),))


def demo_photos() -> list[Photo]:
    d = datetime
    burst = fake_uuid("eiffel-burst-1")
    dup = fake_uuid("kinkaku-pond-a")
    return [
        # A Saturday at home
        shot(
            "home-garden-a",
            d(2026, 5, 2, 10, 5, 0, tzinfo=PDT),
            "apple_park",
            overall=0.62,
            curation=0.71,
            sharpness=0.70,
            composition=0.50,
            faces=2,
            persons=2,
        ),
        shot(
            "home-garden-b",
            d(2026, 5, 2, 10, 5, 2, tzinfo=PDT),
            "apple_park",
            overall=0.58,
            curation=0.69,
            sharpness=0.66,
            composition=0.48,
            faces=2,
            persons=2,
        ),
        shot(
            "home-screenshot", d(2026, 5, 2, 11, 30, tzinfo=PDT), "apple_park", is_screenshot=True
        ),
        shot(
            "home-dinner",
            d(2026, 5, 2, 19, 40, tzinfo=PDT),
            "apple_park",
            overall=0.40,
            curation=0.55,
            sharpness=0.30,
            composition=0.20,
            faces=3,
            persons=3,
        ),
        # Day out in the city, inside the "Golden Gate Park" geofence
        shot(
            "ggp-meadow",
            d(2026, 5, 9, 14, 10, tzinfo=PDT),
            "golden_gate_park",
            overall=0.55,
            curation=0.60,
            sharpness=0.80,
            composition=0.60,
        ),
        shot(
            "ggp-running",
            d(2026, 5, 9, 14, 40, tzinfo=PDT),
            "golden_gate_park",
            overall=0.30,
            curation=0.40,
            sharpness=-0.70,
            composition=0.10,
            faces=1,
            persons=1,
        ),
        # Paris, four days
        *[
            shot(
                f"eiffel-burst-{i}",
                d(2026, 5, 21, 18, 0, i, tzinfo=CEST),
                "eiffel_tower",
                overall=o,
                curation=0.72,
                sharpness=s,
                composition=0.55,
                faces=1,
                persons=1,
                burst_group=burst,
                burst_pick=(i == 3),
            )
            for i, (o, s) in enumerate(
                [(0.50, 0.40), (0.66, 0.75), (0.61, 0.70), (0.64, 0.72)], start=1
            )
        ],
        shot(
            "eiffel-night",
            d(2026, 5, 21, 21, 45, tzinfo=CEST),
            "eiffel_tower",
            overall=0.74,
            curation=0.82,
            sharpness=0.62,
            composition=0.71,
        ),
        shot(
            "louvre-pyramid",
            d(2026, 5, 22, 10, 20, tzinfo=CEST),
            "louvre",
            overall=0.58,
            curation=0.64,
            sharpness=0.81,
            composition=0.66,
        ),
        shot(
            "louvre-selfie",
            d(2026, 5, 22, 10, 31, tzinfo=CEST),
            "louvre",
            overall=0.35,
            curation=0.58,
            sharpness=0.52,
            composition=0.30,
            faces=2,
            persons=2,
        ),
        shot(
            "versailles-hall",
            d(2026, 5, 23, 11, 2, tzinfo=CEST),
            "versailles",
            overall=0.69,
            curation=0.77,
            sharpness=0.58,
            composition=0.62,
        ),
        shot(
            "versailles-garden",
            d(2026, 5, 23, 15, 12, tzinfo=CEST),
            "versailles",
            overall=0.21,
            curation=0.42,
            sharpness=0.12,
            composition=0.18,
        ),
        shot(
            "eiffel-farewell",
            d(2026, 5, 24, 9, 15, tzinfo=CEST),
            "eiffel_tower",
            overall=0.47,
            curation=0.61,
            sharpness=0.44,
            composition=0.40,
            faces=2,
            persons=2,
        ),
        shot(
            "paris-fresh-sync",
            d(2026, 5, 24, 9, 40, tzinfo=CEST),
            "eiffel_tower",
            overall=None,
            curation=None,
            sharpness=None,
            composition=None,
        ),
        # Kyoto, three days
        shot(
            "fushimi-gates",
            d(2026, 6, 3, 8, 10, tzinfo=JST),
            "fushimi_inari",
            overall=0.81,
            curation=0.86,
            sharpness=0.77,
            composition=0.80,
        ),
        shot(
            "fushimi-climb",
            d(2026, 6, 3, 9, 5, tzinfo=JST),
            "fushimi_inari",
            overall=0.45,
            curation=0.59,
            sharpness=0.50,
            composition=0.35,
            faces=1,
            persons=1,
        ),
        shot(
            "fushimi-fox",
            d(2026, 6, 3, 9, 6, tzinfo=JST),
            "fushimi_inari",
            overall=0.52,
            curation=0.60,
            sharpness=0.60,
            composition=0.48,
        ),
        shot(
            "kinkaku-pond-a",
            d(2026, 6, 4, 10, 0, tzinfo=JST),
            "kinkaku_ji",
            overall=0.78,
            curation=0.84,
            sharpness=0.74,
            composition=0.79,
            duplicate_group=dup,
        ),
        shot(
            "kinkaku-pond-b",
            d(2026, 6, 4, 10, 1, tzinfo=JST),
            "kinkaku_ji",
            overall=0.78,
            curation=0.84,
            sharpness=0.74,
            composition=0.79,
            duplicate_group=dup,
        ),
        shot(
            "kinkaku-video",
            d(2026, 6, 4, 10, 5, tzinfo=JST),
            "kinkaku_ji",
            media_type=MediaType.VIDEO,
        ),
        shot(
            "kyoto-station",
            d(2026, 6, 5, 17, 30, tzinfo=JST),
            "fushimi_inari",
            overall=0.10,
            curation=0.35,
            sharpness=0.20,
            composition=0.10,
        ),
        # Back home
        shot(
            "home-bbq",
            d(2026, 6, 14, 18, 20, tzinfo=PDT),
            "apple_park",
            overall=0.71,
            curation=0.80,
            sharpness=0.68,
            composition=0.64,
            faces=4,
            persons=3,
        ),
        shot(
            "scanned-print",
            d(2026, 6, 14, 20, 0, tzinfo=PDT),
            overall=0.20,
            curation=0.40,
            sharpness=0.10,
            composition=0.20,
        ),
        # Taken this morning: the day is not over, so no suggestion yet
        shot(
            "today-coffee",
            d(2026, 6, 20, 9, 0, tzinfo=PDT),
            "apple_park",
            overall=0.72,
            curation=0.78,
            sharpness=0.74,
            composition=0.66,
            faces=1,
            persons=1,
        ),
    ]
