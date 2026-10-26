"""Desired-state planning: what albums every photo belongs in, minus what is already there.

The planner is a pure function. It reads photos and the state snapshot, and returns a ``Plan``.
Applying the plan is the runner's job.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, time, timedelta

from photosorg import naming, scoring, trips
from photosorg.config import Config
from photosorg.models import Membership, Photo, Plan, ScoredPhoto


@dataclass(frozen=True, slots=True)
class StateView:
    """The parts of the state DB the planner needs, as plain values."""

    memberships: frozenset[Membership] = frozenset()
    known_trips: tuple[trips.KnownTrip, ...] = ()
    suggested_events: frozenset[str] = frozenset()


def in_scope(photo: Photo, cfg: Config) -> bool:
    return photo.media_type in cfg.media and not photo.is_hidden


def event_key(photo: Photo, trip_of: dict[str, str], group_by: str = "day") -> str:
    """``day:YYYY-MM-DD``, or the trip name when grouping by event and the photo is on a trip."""
    if group_by == "event" and photo.uuid in trip_of:
        return f"trip:{trip_of[photo.uuid]}"
    return f"day:{photo.day.isoformat()}"


def is_settled(members: Sequence[Photo], now: datetime, settle_hours: int) -> bool:
    """An event is settled once its last day is over plus a grace period for late syncs."""
    last = max(members, key=lambda p: p.taken_at).taken_at
    boundary = datetime.combine(last.date() + timedelta(days=1), time(0), tzinfo=last.tzinfo)
    boundary += timedelta(hours=settle_hours)
    if (boundary.tzinfo is None) != (now.tzinfo is None):
        now = now.replace(tzinfo=boundary.tzinfo)
    return now >= boundary


def build_plan(photos: Iterable[Photo], cfg: Config, state: StateView, now: datetime) -> Plan:
    scope = sorted((p for p in photos if in_scope(p, cfg)), key=lambda p: (p.taken_at, p.uuid))
    plan = Plan(seen=[p.uuid for p in scope], latest=scope[-1].taken_at if scope else None)
    desired: set[Membership] = set()

    for p in scope:
        desired.update(Membership(a, p.uuid) for a in naming.albums_for(p, cfg))

    plan.trips = trips.detect(scope, cfg, state.known_trips)
    trip_of: dict[str, str] = {}
    for t in plan.trips:
        for u in t.uuids:
            trip_of[u] = t.name
            desired.add(Membership(t.name, u))

    fav = cfg.favourites
    if fav.enabled:
        plan.scored = scoring.score_all(scope, fav)
        events: dict[str, list[ScoredPhoto]] = defaultdict(list)
        for sp in plan.scored:
            events[event_key(sp.photo, trip_of, fav.group_by)].append(sp)
        for key in sorted(events):
            members = events[key]
            if key in state.suggested_events:
                continue
            if not is_settled([sp.photo for sp in members], now, fav.settle_hours):
                continue
            plan.settled_events.append(key)
            for sp in scoring.top_n(members, fav):
                plan.suggestions.append(sp)
                desired.add(Membership(fav.album, sp.photo.uuid))

    plan.to_add = sorted(desired - state.memberships)
    plan.already_present = len(desired & state.memberships)
    return plan
