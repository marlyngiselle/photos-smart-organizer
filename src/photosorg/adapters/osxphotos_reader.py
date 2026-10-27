"""Read-only adapter over osxphotos.

osxphotos reads a copy-safe view of the Photos SQLite database. It never writes to the library.
The import is lazy so the rest of the package (and CI on Linux) works without it.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from datetime import datetime
from typing import Any

from photosorg.models import MediaType, Photo, Scores

UNKNOWN_PERSON = "_UNKNOWN_"


def _blocked_by_macos(exc: BaseException) -> bool:
    """osxphotos wraps the PermissionError from privacy protection in one or more OSErrors."""
    cause: BaseException | None = exc
    while cause is not None:
        if isinstance(cause, PermissionError):
            return True
        cause = cause.__cause__
    return False


class ReaderUnavailable(RuntimeError):
    pass


def _first(values: Any) -> str | None:
    if not values:
        return None
    return str(values[0]) or None


def _score(info: Any, name: str) -> float | None:
    value = getattr(info, name, None) if info is not None else None
    return None if value is None else float(value)


def to_photo(p: Any) -> Photo:
    """Map an osxphotos ``PhotoInfo`` (or anything shaped like it) to a ``Photo``."""
    lat, lon = p.location if p.location else (None, None)
    country = city = None
    place = getattr(p, "place", None)
    if place is not None and getattr(place, "names", None) is not None:
        country = _first(place.names.country)
        city = _first(place.names.city)

    if p.ismovie:
        media = MediaType.VIDEO
    elif getattr(p, "live_photo", False):
        media = MediaType.LIVE
    else:
        media = MediaType.PHOTO

    burst_group = None
    if getattr(p, "burst", False):
        key = p.burst_key_photo
        burst_group = (
            key.uuid if key is not None else min([p.uuid, *(b.uuid for b in p.burst_photos)])
        )
    dups = getattr(p, "duplicates", None) or []
    duplicate_group = min([p.uuid, *(d.uuid for d in dups)]) if dups else None

    info = getattr(p, "score", None)
    scores = Scores(
        overall=_score(info, "overall"),
        curation=_score(info, "curation"),
        sharpness=_score(info, "sharply_focused_subject"),
        composition=_score(info, "well_framed_subject"),
    )
    if all(v == 0 for v in (scores.overall, scores.curation, scores.sharpness, scores.composition)):
        # osxphotos returns an all-zero ScoreInfo when Photos has no analysis for the asset
        # yet (typical for a photo that synced minutes ago). Treat that as "unknown".
        scores = Scores()

    persons = [n for n in (p.persons or []) if n and n != UNKNOWN_PERSON]
    return Photo(
        uuid=p.uuid,
        taken_at=p.date,
        media_type=media,
        latitude=lat,
        longitude=lon,
        country=country,
        city=city,
        faces=len(p.face_info or []),
        persons=len(persons),
        is_screenshot=bool(getattr(p, "screenshot", False)),
        is_favourite=bool(p.favorite),
        is_hidden=bool(p.hidden),
        burst_group=burst_group,
        burst_pick=bool(getattr(p, "burst_selected", False)),
        duplicate_group=duplicate_group,
        scores=scores,
    )


class OsxPhotosReader:
    """Reads the system Photos library, or the one at ``library``, read-only."""

    def __init__(self, library: str | None = None, db: Any = None) -> None:
        self._library = library
        self._db = db

    def _open(self) -> Any:
        if self._db is not None:
            return self._db
        try:
            import osxphotos
        except ImportError as exc:  # pragma: no cover - depends on the host
            raise ReaderUnavailable(
                "osxphotos is not installed. Install with: pip install 'photosorg[macos]'"
            ) from exc
        try:
            self._db = (
                osxphotos.PhotosDB(library_path=self._library)
                if self._library
                else osxphotos.PhotosDB()
            )
        except OSError as exc:
            if not _blocked_by_macos(exc):
                raise
            raise ReaderUnavailable(
                f"macOS blocked reading the Photos library ({sys.executable}). Grant Full Disk "
                "Access to the app running photosorg (Terminal, or this Python for the agent) "
                "in System Settings, Privacy and Security. See docs/troubleshooting.md"
            ) from exc
        return self._db

    def photos(self, since: datetime | None) -> Iterator[Photo]:
        db = self._open()
        for p in db.photos(images=True, movies=True):
            if p.intrash:
                continue
            # A photo taken last month but synced from iCloud today still counts as new.
            newest = max(d for d in (p.date, getattr(p, "date_added", None)) if d is not None)
            if since is not None and newest < since:
                continue
            yield to_photo(p)
