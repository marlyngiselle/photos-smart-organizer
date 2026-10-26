"""LaunchAgent rendering and (un)installation.

The agent runs ``photosorg run --since auto`` every N minutes in the user's session, at low
priority, and logs to ``~/Library/Logs/photosorg``.
"""

from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

LABEL = "io.github.marlyngiselle.photosorg"
AGENTS_DIR = Path("~/Library/LaunchAgents").expanduser()
LOG_DIR = Path("~/Library/Logs/photosorg").expanduser()
Runner = Callable[[list[str]], subprocess.CompletedProcess[str]]


class AgentError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AgentSpec:
    interval_minutes: int
    python: str = sys.executable
    config: Path | None = None
    log_dir: Path = LOG_DIR
    label: str = LABEL

    def program_arguments(self) -> list[str]:
        args = [self.python, "-m", "photosorg"]
        if self.config is not None:
            args += ["--config", str(self.config)]
        return [*args, "run", "--since", "auto"]


def render(spec: AgentSpec) -> bytes:
    if not 5 <= spec.interval_minutes <= 1440:
        raise AgentError("interval must be between 5 and 1440 minutes")
    plist = {
        "Label": spec.label,
        "ProgramArguments": spec.program_arguments(),
        "StartInterval": spec.interval_minutes * 60,
        "RunAtLoad": False,
        "ProcessType": "Background",
        "LowPriorityIO": True,
        "Nice": 10,
        "StandardOutPath": str(spec.log_dir / "photosorg.log"),
        "StandardErrorPath": str(spec.log_dir / "photosorg.err.log"),
        "EnvironmentVariables": {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "PYTHONUNBUFFERED": "1"},
    }
    return plistlib.dumps(plist, fmt=plistlib.FMT_XML, sort_keys=True)


def plist_path(label: str = LABEL, agents_dir: Path = AGENTS_DIR) -> Path:
    return agents_dir / f"{label}.plist"


def _run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, capture_output=True, text=True, check=False)


def lint(path: Path, runner: Runner = _run) -> None:
    proc = runner(["/usr/bin/plutil", "-lint", str(path)])
    if proc.returncode != 0:
        raise AgentError(f"plutil rejected {path}: {proc.stdout.strip()} {proc.stderr.strip()}")


def write(spec: AgentSpec, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = plist_path(spec.label, directory)
    path.write_bytes(render(spec))
    return path


def install(
    spec: AgentSpec, runner: Runner = _run, agents_dir: Path = AGENTS_DIR, load: bool = True
) -> Path:
    spec.log_dir.mkdir(parents=True, exist_ok=True)
    path = write(spec, agents_dir)
    lint(path, runner)
    if load:
        domain = f"gui/{os.getuid()}"
        runner(["/bin/launchctl", "bootout", f"{domain}/{spec.label}"])  # fine if not loaded
        proc = runner(["/bin/launchctl", "bootstrap", domain, str(path)])
        if proc.returncode != 0:
            raise AgentError(f"launchctl bootstrap failed: {proc.stderr.strip()}")
    return path


def uninstall(label: str = LABEL, runner: Runner = _run, agents_dir: Path = AGENTS_DIR) -> bool:
    path = plist_path(label, agents_dir)
    runner(["/bin/launchctl", "bootout", f"gui/{os.getuid()}/{label}"])
    if path.exists():
        path.unlink()
        return True
    return False
