"""Favourite recommendation.

Every eligible photo gets a 0..1 score built from signals Photos already computed, minus explicit
penalties. Bursts, Photos-detected duplicates and near-duplicates (shots seconds apart with
almost the same score) keep only their best frame. The top N per event are suggested.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import replace

from photosorg.config import FavouriteRules
from photosorg.models import MediaType, Photo, ScoredPhoto, Signal

NEUTRAL = 0.5


def _unit(value: float | None, signed: bool) -> float | None:
    """Map Photos' -1..1 (signed) or 0..1 scales onto 0..1."""
    if value is None:
        return None
    v = (value + 1) / 2 if signed else value
    return max(0.0, min(1.0, v))


def exclusion(photo: Photo, rules: FavouriteRules) -> str | None:
    if photo.media_type is MediaType.VIDEO:
        return "video"
    if photo.is_screenshot:
        return "screenshot"
    if photo.is_hidden:
        return "hidden"
    if rules.skip_existing_favourites and photo.is_favourite:
        return "already a favourite"
    return None


def score(photo: Photo, rules: FavouriteRules) -> ScoredPhoto:
    w, pen, s = rules.weights, rules.penalties, photo.scores
    signals: list[Signal] = []

    def add(name: str, raw: float | None, value: float | None, weight: float) -> None:
        used = NEUTRAL if value is None else value
        note = "not analysed yet, neutral" if value is None else ""
        signals.append(Signal(name, raw, round(weight * used, 4), note))

    add("aesthetic", s.overall, _unit(s.overall, signed=True), w.aesthetic)
    add("curation", s.curation, _unit(s.curation, signed=False), w.curation)
    sharp = _unit(s.sharpness, signed=True)
    add("sharpness", s.sharpness, sharp, w.sharpness)
    add("composition", s.composition, _unit(s.composition, signed=True), w.composition)
    add("faces", float(photo.faces), 1.0 if photo.faces > 0 else 0.0, w.faces)
    add("people", float(photo.persons), min(photo.persons, 4) / 4, w.people)

    if sharp is not None and sharp < pen.blurry_threshold:
        signals.append(
            Signal("blurry", sharp, -pen.blurry, f"sharpness below {pen.blurry_threshold}")
        )
    if s.overall is None:
        signals.append(Signal("unanalysed", None, -pen.unanalysed, "Photos has not scored it yet"))

    total = max(0.0, min(1.0, sum(sig.contribution for sig in signals)))
    return ScoredPhoto(photo, round(total, 4), tuple(signals), exclusion(photo, rules))


def _rank_key(sp: ScoredPhoto) -> tuple[float, int, str]:
    # Highest score first; on a tie prefer the frame the user picked, then a stable uuid order.
    return (-sp.score, 0 if sp.photo.burst_pick else 1, sp.photo.uuid)


def _keep_best(
    items: list[ScoredPhoto], key: Callable[[ScoredPhoto], str | None], label: str
) -> list[ScoredPhoto]:
    groups: dict[str, list[int]] = defaultdict(list)
    for i, sp in enumerate(items):
        k = key(sp)
        if k is not None and sp.eligible:
            groups[k].append(i)
    out = list(items)
    for idxs in groups.values():
        if len(idxs) < 2:
            continue
        best = min(idxs, key=lambda i: _rank_key(items[i]))
        for i in idxs:
            if i != best:
                out[i] = replace(
                    items[i], excluded_reason=f"{label}, kept {items[best].photo.uuid[:8]}"
                )
    return out


def near_duplicate_groups(items: Sequence[ScoredPhoto], rules: FavouriteRules) -> dict[str, str]:
    """uuid -> group id for eligible photos taken within N seconds with a similar score."""
    eligible = sorted(
        (sp for sp in items if sp.eligible), key=lambda sp: (sp.photo.taken_at, sp.photo.uuid)
    )
    group: dict[str, str] = {}
    prev: ScoredPhoto | None = None
    for sp in eligible:
        if prev is not None:
            dt = (sp.photo.taken_at - prev.photo.taken_at).total_seconds()
            close = dt <= rules.near_duplicate_seconds
            similar = abs(sp.score - prev.score) <= rules.near_duplicate_score_delta
            if close and similar:
                group[sp.photo.uuid] = group.setdefault(prev.photo.uuid, prev.photo.uuid)
        prev = sp
    return group


def dedupe(items: Sequence[ScoredPhoto], rules: FavouriteRules) -> list[ScoredPhoto]:
    out = _keep_best(list(items), lambda sp: sp.photo.burst_group, "burst")
    out = _keep_best(out, lambda sp: sp.photo.duplicate_group, "duplicate")
    groups = near_duplicate_groups(out, rules)
    return _keep_best(out, lambda sp: groups.get(sp.photo.uuid), "near-duplicate")


def score_all(photos: Iterable[Photo], rules: FavouriteRules) -> list[ScoredPhoto]:
    return dedupe([score(p, rules) for p in photos], rules)


def top_n(items: Iterable[ScoredPhoto], rules: FavouriteRules) -> list[ScoredPhoto]:
    ranked = sorted(
        (sp for sp in items if sp.eligible and sp.score >= rules.min_score), key=_rank_key
    )
    return ranked[: rules.top_n_per_event]
