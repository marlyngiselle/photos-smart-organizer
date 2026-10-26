"""The two seams between pure logic and the Mac. Tests plug fakes in here."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from datetime import datetime
from typing import Protocol, runtime_checkable

from photosorg.models import Photo


@runtime_checkable
class PhotoReader(Protocol):
    """Read-only view of the library. Implementations must never write to it."""

    def photos(self, since: datetime | None) -> Iterator[Photo]: ...


@runtime_checkable
class PhotoWriter(Protocol):
    """Album membership and keywords only. No method may delete or edit a photo."""

    def ensure_album(self, folder: str, album: str) -> bool:
        """Create the album inside ``folder`` if missing. Returns True when it was created."""
        ...

    def add_to_album(self, folder: str, album: str, uuids: Sequence[str]) -> None: ...

    def remove_from_album(self, folder: str, album: str, uuids: Sequence[str]) -> None: ...

    def delete_album(self, folder: str, album: str) -> None:
        """Delete an empty album the tool created. Photos are never deleted with it."""
        ...

    def add_keyword(self, uuids: Sequence[str], keyword: str) -> None: ...

    def remove_keyword(self, uuids: Sequence[str], keyword: str) -> None: ...
