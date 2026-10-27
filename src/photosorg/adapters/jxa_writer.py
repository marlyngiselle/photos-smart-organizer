"""Writes album membership through Photos' own scripting interface (JXA via osascript).

Every call is a separate, short ``osascript`` process. The first one triggers the macOS
Automation prompt ("python wants to control Photos"), which the user approves once.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Sequence
from importlib.resources import as_file, files
from pathlib import Path

OSASCRIPT = "/usr/bin/osascript"
Runner = Callable[[list[str]], str]


class WriterError(RuntimeError):
    pass


def script_path() -> Path:
    with as_file(files("photosorg.jxa") / "photos_album.js") as path:
        return Path(path)


def _subprocess_runner(argv: list[str]) -> str:
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=600, check=False)
    if proc.returncode != 0:
        raise WriterError(f"osascript failed ({proc.returncode}): {proc.stderr.strip()}")
    return proc.stdout.strip()


class JxaPhotosWriter:
    def __init__(self, runner: Runner = _subprocess_runner, script: Path | None = None) -> None:
        self._run = runner
        self._script = script or script_path()

    def _call(self, *args: str) -> str:
        return self._run([OSASCRIPT, "-l", "JavaScript", str(self._script), *args])

    def ensure_album(self, folder: str, album: str) -> bool:
        return self._call("ensure", folder, album) == "created"

    def add_to_album(self, folder: str, album: str, uuids: Sequence[str]) -> list[str]:
        """Add what Photos can resolve; return the uuids it could not find."""
        if not uuids:
            return []
        out = self._call("add", folder, album, *uuids)
        try:
            missing = json.loads(out).get("missing", [])
        except (ValueError, AttributeError):
            return []
        return [str(u) for u in missing]

    def remove_from_album(self, folder: str, album: str, uuids: Sequence[str]) -> None:
        if uuids:
            self._call("remove", folder, album, *uuids)

    def delete_album(self, folder: str, album: str) -> None:
        self._call("delete", folder, album)

    def add_keyword(self, uuids: Sequence[str], keyword: str) -> None:
        if uuids:
            self._call("kw-add", keyword, *uuids)

    def remove_keyword(self, uuids: Sequence[str], keyword: str) -> None:
        if uuids:
            self._call("kw-remove", keyword, *uuids)
