"""In-memory reader and writer. Used by the test suite and by ``--demo``."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import datetime

from photosorg.models import Photo


class MemoryReader:
    def __init__(self, photos: Iterable[Photo]) -> None:
        self._photos = list(photos)

    def photos(self, since: datetime | None) -> Iterator[Photo]:
        for p in self._photos:
            if since is None or p.taken_at >= since:
                yield p


@dataclass
class MemoryWriter:
    """Behaves like the Photos writer and records every call it receives."""

    albums: dict[tuple[str, str], list[str]] = field(default_factory=dict)
    keywords: dict[str, set[str]] = field(default_factory=dict)
    calls: list[tuple[str, ...]] = field(default_factory=list)
    fail_on: str | None = None
    unreachable: set[str] = field(default_factory=set)

    def _call(self, *args: str) -> None:
        self.calls.append(args)
        if self.fail_on is not None and args[0] == self.fail_on:
            raise RuntimeError(f"injected failure on {args[0]}")

    def ensure_album(self, folder: str, album: str) -> bool:
        self._call("ensure", folder, album)
        if (folder, album) in self.albums:
            return False
        self.albums[(folder, album)] = []
        return True

    def add_to_album(self, folder: str, album: str, uuids: Sequence[str]) -> list[str]:
        self._call("add", folder, album, *uuids)
        members = self.albums.setdefault((folder, album), [])
        members.extend(u for u in uuids if u not in members and u not in self.unreachable)
        return [u for u in uuids if u in self.unreachable]

    def remove_from_album(self, folder: str, album: str, uuids: Sequence[str]) -> None:
        self._call("remove", folder, album, *uuids)
        drop = set(uuids)
        self.albums[(folder, album)] = [
            u for u in self.albums.get((folder, album), []) if u not in drop
        ]

    def delete_album(self, folder: str, album: str) -> None:
        self._call("delete", folder, album)
        self.albums.pop((folder, album), None)

    def add_keyword(self, uuids: Sequence[str], keyword: str) -> None:
        self._call("kw-add", keyword, *uuids)
        for u in uuids:
            self.keywords.setdefault(u, set()).add(keyword)

    def remove_keyword(self, uuids: Sequence[str], keyword: str) -> None:
        self._call("kw-remove", keyword, *uuids)
        for u in uuids:
            self.keywords.get(u, set()).discard(keyword)
