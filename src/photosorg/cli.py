"""Command line interface.

``photosorg run | plan | stats | undo | install-agent | uninstall-agent``
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from photosorg import __version__, config, launchd, report, runner
from photosorg.adapters.osxphotos_reader import ReaderUnavailable
from photosorg.ports import PhotoReader, PhotoWriter
from photosorg.state import DEFAULT_STATE_PATH, StateStore

log = logging.getLogger("photosorg")


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="photosorg",
        description="Files new Apple Photos into albums by place, date and trip, and suggests "
        "favourites. Reads the library read-only; writes album membership only.",
    )
    p.add_argument("--version", action="version", version=f"photosorg {__version__}")
    p.add_argument(
        "--config", type=Path, help=f"TOML config (default {config.DEFAULT_CONFIG_PATH})"
    )
    p.add_argument("--state", type=Path, help=f"SQLite state DB (default {DEFAULT_STATE_PATH})")
    p.add_argument(
        "--demo",
        action="store_true",
        help="use the built-in synthetic library and an in-memory writer",
    )
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)

    since_help = "auto (default), all, or an ISO date such as 2026-01-01"
    r = sub.add_parser("run", help="plan and apply: add photos to albums")
    r.add_argument("--since", default="auto", help=since_help)
    r.add_argument("--dry-run", action="store_true", help="plan only, change nothing")

    pl = sub.add_parser("plan", help="show what a run would do")
    pl.add_argument("--since", default="auto", help=since_help)
    pl.add_argument("--explain", action="store_true", help="show the score of every photo")
    pl.add_argument("--limit", type=int, help="explain at most N photos")

    sub.add_parser("stats", help="what the tool has done so far")

    u = sub.add_parser("undo", help="remove the album memberships a run created")
    u.add_argument("--run", required=True, dest="run_id", help="run id, see `photosorg stats`")
    u.add_argument("--dry-run", action="store_true")

    ia = sub.add_parser("install-agent", help="install the launchd LaunchAgent")
    ia.add_argument("--interval", type=int, help="minutes between runs (default from config)")
    ia.add_argument("--at", metavar="HH:MM", help="run once a day at this time instead")
    ia.add_argument(
        "--render-only",
        action="store_true",
        help="write the plist to --output and stop (used by CI)",
    )
    ia.add_argument("--output", type=Path, default=Path.cwd(), help="directory for --render-only")
    ia.add_argument("--no-load", action="store_true", help="install the file, do not bootstrap")

    sub.add_parser("uninstall-agent", help="unload and remove the LaunchAgent")
    return p


def _adapters(
    args: argparse.Namespace, cfg: config.Config
) -> tuple[PhotoReader, PhotoWriter, datetime]:
    if args.demo:
        from photosorg import fixtures
        from photosorg.adapters.memory import MemoryReader, MemoryWriter

        return MemoryReader(fixtures.demo_photos()), MemoryWriter(), fixtures.DEMO_NOW
    from photosorg.adapters.jxa_writer import JxaPhotosWriter
    from photosorg.adapters.osxphotos_reader import OsxPhotosReader

    return OsxPhotosReader(cfg.library), JxaPhotosWriter(), datetime.now(UTC)


def _state(args: argparse.Namespace) -> StateStore:
    if args.state is not None:
        return StateStore(args.state)
    return StateStore(":memory:") if args.demo else StateStore(DEFAULT_STATE_PATH)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    try:
        cfg = config.load(args.config)
        if args.demo and args.config is None:
            from photosorg import fixtures

            cfg = fixtures.demo_config()
        return _dispatch(args, cfg)
    except (
        config.ConfigError,
        runner.UndoError,
        launchd.AgentError,
        ReaderUnavailable,
        ValueError,
    ) as exc:
        print(f"photosorg: {exc}", file=sys.stderr)
        return 2


def _dispatch(args: argparse.Namespace, cfg: config.Config) -> int:
    if args.command == "install-agent":
        daily_at = launchd.parse_time(args.at) if args.at else None
        spec = launchd.AgentSpec(
            args.interval or cfg.interval_minutes, config=args.config, daily_at=daily_at
        )
        if args.render_only:
            print(launchd.write(spec, args.output))
            return 0
        path = launchd.install(spec, load=not args.no_load)
        when = f"daily at {args.at}" if daily_at else f"every {spec.interval_minutes} min"
        print(f"installed {path}, {when}, logs in {spec.log_dir}")
        return 0
    if args.command == "uninstall-agent":
        print("removed" if launchd.uninstall() else "no agent installed")
        return 0

    state = _state(args)
    try:
        if args.command == "stats":
            print(report.render_stats(state.stats(), state.runs()))
            return 0
        if args.command == "undo":
            _, writer, _ = _adapters(args, cfg)
            undone = runner.undo(args.run_id, writer, state, cfg, dry_run=args.dry_run)
            verb = "would remove" if args.dry_run else "removed"
            print(
                f"{verb} {undone.removed} memberships, {undone.keywords_removed} keywords; "
                f"albums deleted: {', '.join(undone.albums_deleted) or 'none'}"
            )
            return 0
        reader, writer, now = _adapters(args, cfg)
        if args.command == "plan":
            plan = runner.make_plan(reader, state, cfg, args.since, now)
            print(report.render_plan(plan, cfg.folder, explain=args.explain, limit=args.limit))
            return 0
        if args.command == "run":
            res = runner.run(
                reader, writer, state, cfg, since=args.since, dry_run=args.dry_run, now=now
            )
            if res.dry_run:
                print(report.render_plan(res.plan, cfg.folder))
            else:
                log.info(
                    "run %s: %d additions, %d new albums, %d suggestions",
                    res.run_id,
                    res.added,
                    res.albums_created,
                    len(res.plan.suggestions),
                )
            return 0
    finally:
        state.close()
    return 1  # pragma: no cover - argparse guarantees a known command
