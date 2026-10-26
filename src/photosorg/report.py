"""Plain-text rendering for the CLI. Deterministic, so it can be snapshot-tested."""

from __future__ import annotations

from collections.abc import Sequence

from photosorg.models import Plan, ScoredPhoto
from photosorg.state import RunRecord


def _short(uuid: str) -> str:
    return uuid[:8]


def render_plan(plan: Plan, folder: str, explain: bool = False, limit: int | None = None) -> str:
    lines: list[str] = []
    albums = plan.albums()
    lines.append(
        f'Folder "{folder}"  |  {plan.photos_seen} photos in scope  |  '
        f"{len(plan.to_add)} additions to {len(albums)} albums  |  "
        f"{plan.already_present} already filed"
    )
    lines.append("")
    lines.append("Albums")
    if not albums:
        lines.append("  nothing to add, the library is already organised")
    width = max((len(a) for a in albums), default=10)
    for album, uuids in albums.items():
        lines.append(f"  + {album:<{width}}  {len(uuids):>4}")

    if plan.trips:
        lines.append("")
        lines.append("Trips")
        for t in plan.trips:
            lines.append(
                f"  {t.name:<{width}}  {t.start.isoformat()} to {t.end.isoformat()}"
                f"  {len(t.uuids)} photos"
            )

    lines.append("")
    lines.append(f"Suggested favourites ({len(plan.suggestions)})")
    if not plan.suggestions:
        lines.append("  none this time")
    for sp in plan.suggestions:
        lines.append(
            f"  {_short(sp.photo.uuid)}  {sp.photo.taken_at:%Y-%m-%d %H:%M}  "
            f"{(sp.photo.city or 'no location'):<14} {sp.score:.3f}"
        )

    if explain:
        lines.append("")
        lines += render_explain(plan.scored, {s.photo.uuid for s in plan.suggestions}, limit)
    return "\n".join(lines)


def render_explain(
    scored: Sequence[ScoredPhoto], suggested: set[str], limit: int | None = None
) -> list[str]:
    lines = ["Score breakdown (signal, raw value from Photos, contribution)"]
    items = sorted(scored, key=lambda sp: (sp.photo.taken_at, sp.photo.uuid))
    for sp in items[:limit] if limit else items:
        if sp.photo.uuid in suggested:
            verdict = "SUGGESTED"
        elif sp.excluded_reason:
            verdict = f"skipped: {sp.excluded_reason}"
        else:
            verdict = "eligible"
        lines.append("")
        lines.append(
            f"  {_short(sp.photo.uuid)}  {sp.photo.taken_at:%Y-%m-%d %H:%M}  "
            f"{sp.photo.city or 'no location'}  score {sp.score:.3f}  {verdict}"
        )
        for sig in sp.signals:
            raw = "   n/a" if sig.raw is None else f"{sig.raw:>6.2f}"
            note = f"  ({sig.note})" if sig.note else ""
            lines.append(f"      {sig.name:<12}{raw}  {sig.contribution:>+7.3f}{note}")
    return lines


def render_stats(stats: dict[str, object], runs: Sequence[RunRecord]) -> str:
    lines = [
        f"Runs                {stats['runs']} ({stats['runs_ok']} ok)",
        f"Photos processed    {stats['photos_processed']}",
        f"Album memberships   {stats['memberships']} across {stats['albums']} albums",
        f"Trips               {stats['trips']}",
        f"Events evaluated    {stats['suggested_events']}",
    ]
    per_album = stats.get("per_album")
    if isinstance(per_album, dict) and per_album:
        lines.append("")
        width = max(len(str(a)) for a in per_album)
        lines += [f"  {a:<{width}}  {n:>5}" for a, n in per_album.items()]
    if runs:
        lines.append("")
        lines.append("Recent runs")
        lines += [f"  {r.id}  {r.status:<7} +{r.added}" for r in runs[-10:]]
    return "\n".join(lines)
