from __future__ import annotations

from dataclasses import replace
from datetime import datetime

import pytest
from hypothesis import given
from hypothesis import strategies as st

from conftest import by_label
from photosorg.config import FavouriteRules
from photosorg.fixtures import PDT, shot
from photosorg.models import MediaType, Photo, Scores
from photosorg.scoring import dedupe, score, score_all, top_n

RULES = FavouriteRules()
T = datetime(2026, 5, 2, 10, 0, tzinfo=PDT)


def test_contributions_add_up_to_the_score(photos: list[Photo]) -> None:
    for p in photos:
        sp = score(p, RULES)
        assert sp.score == pytest.approx(
            max(0.0, min(1.0, sum(s.contribution for s in sp.signals))), abs=1e-3
        )


def test_best_possible_photo_scores_one() -> None:
    p = Photo("u", T, scores=Scores(1.0, 1.0, 1.0, 1.0), faces=3, persons=4)
    assert score(p, RULES).score == 1.0


def test_unanalysed_photo_is_neutral_minus_small_penalty() -> None:
    sp = score(Photo("u", T), RULES)
    assert sp.score == pytest.approx(0.5 * 0.80 - 0.05)
    assert any(s.name == "unanalysed" for s in sp.signals)
    assert all("neutral" in s.note for s in sp.signals[:4])


def test_blurry_penalty_applies_below_threshold() -> None:
    sharp = score(shot("s", T, sharpness=0.5), RULES)
    blurry = score(shot("b", T, sharpness=-0.8), RULES)
    assert any(s.name == "blurry" for s in blurry.signals)
    assert not any(s.name == "blurry" for s in sharp.signals)
    assert sharp.score - blurry.score > 0.30


@pytest.mark.parametrize(
    ("extra", "reason"),
    [
        ({"is_screenshot": True}, "screenshot"),
        ({"media_type": MediaType.VIDEO}, "video"),
        ({"is_hidden": True}, "hidden"),
        ({"is_favourite": True}, "already a favourite"),
    ],
)
def test_exclusions(extra: dict[str, object], reason: str) -> None:
    assert score(shot("x", T, **extra), RULES).excluded_reason == reason


def test_existing_favourites_can_be_kept_in_play() -> None:
    rules = replace(RULES, skip_existing_favourites=False)
    assert score(shot("x", T, is_favourite=True), rules).eligible


def test_burst_keeps_only_the_best_frame(photos: list[Photo]) -> None:
    burst = [p for p in photos if p.burst_group]
    out = dedupe([score(p, RULES) for p in burst], RULES)
    kept = [sp for sp in out if sp.eligible]
    assert len(burst) == 4 and len(kept) == 1
    assert kept[0].photo.uuid == by_label(photos, "eiffel-burst-2").uuid
    assert all(
        sp.excluded_reason == f"burst, kept {kept[0].photo.uuid[:8]}"
        for sp in out
        if not sp.eligible
    )


def test_burst_tie_prefers_the_users_pick() -> None:
    a = shot("a", T, burst_group="g")
    b = shot("b", T, burst_group="g", burst_pick=True)
    kept = [sp for sp in dedupe([score(a, RULES), score(b, RULES)], RULES) if sp.eligible]
    assert [sp.photo.uuid for sp in kept] == [b.uuid]


def test_photos_detected_duplicates_keep_one(photos: list[Photo]) -> None:
    pair = [p for p in photos if p.duplicate_group]
    out = dedupe([score(p, RULES) for p in pair], RULES)
    assert sum(sp.eligible for sp in out) == 1


def test_near_duplicates_by_time_and_score(photos: list[Photo]) -> None:
    a, b = by_label(photos, "home-garden-a"), by_label(photos, "home-garden-b")
    out = {sp.photo.uuid: sp for sp in score_all([a, b], RULES)}
    assert out[a.uuid].eligible
    assert out[b.uuid].excluded_reason == f"near-duplicate, kept {a.uuid[:8]}"


def test_close_in_time_but_different_score_is_not_a_duplicate() -> None:
    a = shot("a", T, overall=0.9, curation=0.9)
    b = shot("b", T, overall=-0.5, curation=0.1)
    assert all(sp.eligible for sp in score_all([a, b], RULES))


def test_near_duplicate_chains_collapse_to_one() -> None:
    frames = [shot(f"f{i}", T.replace(second=i * 2)) for i in range(5)]
    assert sum(sp.eligible for sp in score_all(frames, RULES)) == 1


def test_top_n_respects_threshold_and_count() -> None:
    items = [
        score(
            shot(
                f"p{i}",
                T.replace(minute=i * 5),
                overall=o,
                curation=0.8,
                sharpness=0.6,
                composition=0.6,
            ),
            RULES,
        )
        for i, o in enumerate([0.9, 0.8, 0.7, -0.9])
    ]
    picked = top_n(items, RULES)
    assert [sp.photo.uuid for sp in picked] == [items[0].photo.uuid, items[1].photo.uuid]
    assert top_n(items, replace(RULES, min_score=0.99)) == []


unit = st.floats(min_value=-1, max_value=1, allow_nan=False)


@given(unit, st.floats(0, 1), unit, unit, st.integers(0, 20), st.integers(0, 20))
def test_score_is_always_between_zero_and_one(
    o: float, c: float, s: float, comp: float, faces: int, persons: int
) -> None:
    p = Photo("u", T, scores=Scores(o, c, s, comp), faces=faces, persons=persons)
    assert 0.0 <= score(p, RULES).score <= 1.0


@given(st.floats(min_value=-1, max_value=0.9, allow_nan=False))
def test_higher_aesthetic_never_lowers_the_score(o: float) -> None:
    low = score(Photo("u", T, scores=Scores(o, 0.5, 0.5, 0.5)), RULES).score
    high = score(Photo("u", T, scores=Scores(o + 0.1, 0.5, 0.5, 0.5)), RULES).score
    assert high >= low
