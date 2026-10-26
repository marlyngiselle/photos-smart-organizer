"""Domain types shared by the pure logic and the adapters.

Nothing in this module knows about Photos.app, osxphotos or SQLite. A ``Photo`` is the
read-only snapshot of the metadata Photos already computed for one asset.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum


class MediaType(StrEnum):
    PHOTO = "photo"
    VIDEO = "video"
    LIVE = "live"


@dataclass(frozen=True, slots=True)
class Scores:
    """Subset of Photos' ScoreInfo used by the recommender.

    Photos stores ``overall`` and ``sharpness`` in the range -1..1 and ``curation`` in 0..1.
    ``None`` means Photos has not analysed the asset yet (common for photos that just synced).
    """

    overall: float | None = None
    curation: float | None = None
    sharpness: float | None = None
    composition: float | None = None


@dataclass(frozen=True, slots=True)
class Photo:
    uuid: str
    taken_at: datetime
    media_type: MediaType = MediaType.PHOTO
    latitude: float | None = None
    longitude: float | None = None
    country: str | None = None
    city: str | None = None
    faces: int = 0
    persons: int = 0
    is_screenshot: bool = False
    is_favourite: bool = False
    is_hidden: bool = False
    burst_group: str | None = None
    burst_pick: bool = False
    duplicate_group: str | None = None
    scores: Scores = field(default_factory=Scores)

    @property
    def has_location(self) -> bool:
        return self.latitude is not None and self.longitude is not None

    @property
    def day(self) -> date:
        return self.taken_at.date()


@dataclass(frozen=True, slots=True, order=True)
class Membership:
    """One photo in one album. The unit of work, of state and of undo."""

    album: str
    uuid: str


@dataclass(frozen=True, slots=True)
class Trip:
    name: str
    start: date
    end: date
    city: str
    uuids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Signal:
    """One line of a score explanation."""

    name: str
    raw: float | None
    contribution: float
    note: str = ""


@dataclass(frozen=True, slots=True)
class ScoredPhoto:
    photo: Photo
    score: float
    signals: tuple[Signal, ...]
    excluded_reason: str | None = None

    @property
    def eligible(self) -> bool:
        return self.excluded_reason is None


@dataclass(slots=True)
class Plan:
    """Everything a run would do. Computing it never touches Photos."""

    to_add: list[Membership] = field(default_factory=list)
    already_present: int = 0
    trips: list[Trip] = field(default_factory=list)
    suggestions: list[ScoredPhoto] = field(default_factory=list)
    scored: list[ScoredPhoto] = field(default_factory=list)
    settled_events: list[str] = field(default_factory=list)
    seen: list[str] = field(default_factory=list)
    latest: datetime | None = None

    @property
    def photos_seen(self) -> int:
        return len(self.seen)

    def albums(self) -> dict[str, list[str]]:
        grouped: dict[str, list[str]] = {}
        for m in sorted(self.to_add):
            grouped.setdefault(m.album, []).append(m.uuid)
        return grouped
