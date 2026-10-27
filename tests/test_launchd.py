from __future__ import annotations

import plistlib
import shutil
import subprocess
from pathlib import Path

import pytest

from photosorg import launchd
from photosorg.launchd import AgentError, AgentSpec


def spec(tmp_path: Path, **kw: object) -> AgentSpec:
    return AgentSpec(
        interval_minutes=30, python="/opt/py/bin/python3", log_dir=tmp_path / "logs", **kw
    )  # type: ignore[arg-type]


def test_render_round_trips(tmp_path: Path) -> None:
    data = plistlib.loads(launchd.render(spec(tmp_path)))
    assert data["Label"] == "io.github.marlyngiselle.photosorg"
    assert data["ProgramArguments"] == [
        "/opt/py/bin/python3",
        "-m",
        "photosorg",
        "run",
        "--since",
        "auto",
    ]
    assert data["StartInterval"] == 1800
    assert data["RunAtLoad"] is False
    assert data["ProcessType"] == "Background"
    assert data["StandardOutPath"] == str(tmp_path / "logs" / "photosorg.log")


def test_render_passes_config_path(tmp_path: Path) -> None:
    data = plistlib.loads(launchd.render(spec(tmp_path, config=Path("/c/config.toml"))))
    assert data["ProgramArguments"][3:5] == ["--config", "/c/config.toml"]


def test_render_is_deterministic(tmp_path: Path) -> None:
    assert launchd.render(spec(tmp_path)) == launchd.render(spec(tmp_path))


@pytest.mark.parametrize("minutes", [0, 4, 1441])
def test_interval_bounds(tmp_path: Path, minutes: int) -> None:
    with pytest.raises(AgentError):
        launchd.render(AgentSpec(minutes, log_dir=tmp_path))


def test_daily_at_uses_a_calendar_schedule(tmp_path: Path) -> None:
    data = plistlib.loads(launchd.render(spec(tmp_path, daily_at=(11, 0))))
    assert data["StartCalendarInterval"] == {"Hour": 11, "Minute": 0}
    assert "StartInterval" not in data


@pytest.mark.parametrize(("value", "expected"), [("11:00", (11, 0)), ("7:05", (7, 5))])
def test_parse_time(value: str, expected: tuple[int, int]) -> None:
    assert launchd.parse_time(value) == expected


@pytest.mark.parametrize("value", ["24:00", "11:60", "11", "11h", ""])
def test_parse_time_rejects_bad_input(value: str) -> None:
    with pytest.raises(AgentError):
        launchd.parse_time(value)


class FakeLaunchctl:
    def __init__(self, fail: str | None = None) -> None:
        self.argv: list[list[str]] = []
        self.fail = fail

    def __call__(self, argv: list[str]) -> subprocess.CompletedProcess[str]:
        self.argv.append(argv)
        code = 1 if self.fail and self.fail in argv else 0
        return subprocess.CompletedProcess(argv, code, "", "boom" if code else "")


def test_install_writes_lints_and_bootstraps(tmp_path: Path) -> None:
    fake = FakeLaunchctl()
    path = launchd.install(spec(tmp_path), runner=fake, agents_dir=tmp_path / "agents")
    assert path == tmp_path / "agents" / "io.github.marlyngiselle.photosorg.plist"
    assert (tmp_path / "logs").is_dir()
    verbs = [a[0].rsplit("/", 1)[-1] + " " + a[1] for a in fake.argv]
    assert verbs == ["plutil -lint", "launchctl bootout", "launchctl bootstrap"]


def test_install_reports_bootstrap_failure(tmp_path: Path) -> None:
    with pytest.raises(AgentError, match="bootstrap failed"):
        launchd.install(
            spec(tmp_path), runner=FakeLaunchctl(fail="bootstrap"), agents_dir=tmp_path / "agents"
        )


def test_uninstall(tmp_path: Path) -> None:
    agents = tmp_path / "agents"
    launchd.install(spec(tmp_path), runner=FakeLaunchctl(), agents_dir=agents, load=False)
    assert launchd.uninstall(runner=FakeLaunchctl(), agents_dir=agents) is True
    assert launchd.uninstall(runner=FakeLaunchctl(), agents_dir=agents) is False


@pytest.mark.skipif(shutil.which("plutil") is None, reason="macOS only")
def test_rendered_plist_passes_plutil(tmp_path: Path) -> None:
    path = launchd.write(spec(tmp_path), tmp_path)
    launchd.lint(path)  # real /usr/bin/plutil -lint
