from __future__ import annotations

import plistlib
from pathlib import Path

import pytest

from photosorg.cli import main


def run(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str]:
    code = main(list(argv))
    out, err = capsys.readouterr()
    return code, out + err


def test_demo_plan(capsys: pytest.CaptureFixture[str]) -> None:
    code, out = run(capsys, "--demo", "plan")
    assert code == 0
    assert "Trip · Paris · 2026-05" in out
    assert "Suggested favourites (10)" in out


def test_demo_plan_explain(capsys: pytest.CaptureFixture[str]) -> None:
    code, out = run(capsys, "--demo", "plan", "--explain", "--limit", "4")
    assert code == 0
    assert "Score breakdown" in out
    assert "skipped: screenshot" in out
    assert "skipped: near-duplicate" in out


def test_demo_run_stats_and_undo(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = str(tmp_path / "state.sqlite3")
    assert run(capsys, "--demo", "--state", db, "run")[0] == 0
    code, out = run(capsys, "--demo", "--state", db, "stats")
    assert code == 0 and "Runs                1 (1 ok)" in out
    run_id = out.split("Recent runs")[1].split()[0]
    code, out = run(capsys, "--demo", "--state", db, "undo", "--run", run_id, "--dry-run")
    assert code == 0 and out.startswith("would remove 137 memberships")
    code, out = run(capsys, "--demo", "--state", db, "undo", "--run", run_id)
    assert code == 0 and out.startswith("removed 137 memberships")
    code, out = run(capsys, "--demo", "--state", db, "undo", "--run", run_id)
    assert code == 2 and "already undone" in out


def test_dry_run_prints_the_plan(capsys: pytest.CaptureFixture[str]) -> None:
    code, out = run(capsys, "--demo", "run", "--dry-run")
    assert code == 0 and out.startswith('Folder "Smart Organizer"')


def test_render_agent(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out = run(
        capsys, "install-agent", "--render-only", "--output", str(tmp_path), "--interval", "15"
    )
    assert code == 0
    data = plistlib.loads(Path(out.strip()).read_bytes())
    assert data["StartInterval"] == 900


def test_render_daily_agent(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out = run(
        capsys, "install-agent", "--render-only", "--output", str(tmp_path), "--at", "11:00"
    )
    assert code == 0
    data = plistlib.loads(Path(out.strip()).read_bytes())
    assert data["StartCalendarInterval"] == {"Hour": 11, "Minute": 0}


def test_bad_config_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = tmp_path / "c.toml"
    bad.write_text("[albums]\nby_planet = true\n")
    code, out = run(capsys, "--config", str(bad), "--demo", "plan")
    assert code == 2 and "unknown key" in out
