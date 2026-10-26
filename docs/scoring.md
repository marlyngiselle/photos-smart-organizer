# How scoring works

The recommender never looks at pixels. It reuses the analysis Photos already ran on device and stored in its database, which osxphotos exposes as `ScoreInfo`, and adds a few signals of its own. Every number below is a default from `config.py` and can be changed in `[favourites.weights]` and `[favourites.penalties]`.

## Signals

Each signal is mapped to 0..1 and multiplied by its weight. The weights add up to 1.0, so a perfect photo scores 1.0.

| Signal | Source | Raw range | Mapping to 0..1 | Weight |
| --- | --- | --- | --- | ---: |
| aesthetic | `ScoreInfo.overall` | -1..1 | `(x + 1) / 2` | 0.35 |
| curation | `ScoreInfo.curation` | 0..1 | as is | 0.20 |
| sharpness | `ScoreInfo.sharply_focused_subject` | -1..1 | `(x + 1) / 2` | 0.15 |
| composition | `ScoreInfo.well_framed_subject` | -1..1 | `(x + 1) / 2` | 0.10 |
| faces | face count | 0..n | 1 if any face, else 0 | 0.10 |
| people | named people count | 0..n | `min(n, 4) / 4` | 0.10 |

When Photos has not analysed a photo yet (osxphotos returns an all-zero `ScoreInfo`), the four score signals use a neutral 0.5 and the explanation says so.

## Penalties

| Penalty | Condition | Default |
| --- | --- | ---: |
| blurry | mapped sharpness below `blurry_threshold` (0.25) | -0.30 |
| unanalysed | Photos has no score for the photo yet | -0.05 |

The total is clamped to 0..1.

## Exclusions

These photos are scored, so `plan --explain` can show why, but never suggested.

| Reason | Rule |
| --- | --- |
| screenshot | Photos flags it as a screenshot |
| video | media type is video |
| hidden | it is in the Hidden album |
| already a favourite | you already hearted it (`skip_existing_favourites`) |

## One frame per moment

Three passes, in this order, each keeping only the best photo of a group. Best means highest score; on a tie, the frame you picked in the burst; then a stable UUID order.

| Pass | Group |
| --- | --- |
| burst | Photos' burst set |
| duplicate | Photos' own duplicate detection |
| near-duplicate | Consecutive shots within `near_duplicate_seconds` whose scores differ by at most `near_duplicate_score_delta`. Chains collapse, so five rapid frames keep one |

## Selection

Photos are grouped by day (or by trip with `group_by = "event"`). Once a group is settled, the top `top_n_per_event` photos with a score of at least `min_score` go to "Suggested favourites". A quiet day with nothing above the bar gets no suggestion, which is the point.

## Worked example

From the synthetic demo library (`photosorg --demo plan --explain`), the four frames of a burst at the Eiffel Tower.

```text
  F3647ECA  2026-05-21 18:00  Paris  score 0.768  SUGGESTED
      aesthetic     0.66   +0.290
      curation      0.72   +0.144
      sharpness     0.75   +0.131
      composition   0.55   +0.077
      faces         1.00   +0.100
      people        1.00   +0.025

  69170997  2026-05-21 18:00  Paris  score 0.762  skipped: burst, kept F3647ECA
```

The aesthetic line reads as follows. Photos scored the frame 0.66 on its -1..1 scale, which maps to 0.83, times the 0.35 weight gives 0.290.
