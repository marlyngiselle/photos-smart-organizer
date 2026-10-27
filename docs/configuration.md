# Configuration reference

photosorg reads `~/.config/photosorg/config.toml`, or the file passed with `--config`. Every key is optional. Unknown keys are rejected, so a typo fails loudly instead of being ignored. A complete, commented file with every default is in [`examples/config.toml`](../examples/config.toml).

```bash
mkdir -p ~/.config/photosorg
cp examples/config.toml ~/.config/photosorg/config.toml
```

## `[library]`

| Key | Default | Meaning |
| --- | --- | --- |
| `folder` | `"Smart Organizer"` | Top-level folder in Photos that holds every album the tool creates |
| `path` | system library | Path to another `.photoslibrary` |
| `media` | `["photo", "live"]` | Media types to file. Add `"video"` to include videos (they are never suggested as favourites) |

## `[schedule]`

| Key | Default | Meaning |
| --- | --- | --- |
| `interval_minutes` | `30` | LaunchAgent cadence, 5 to 1440. `install-agent --at HH:MM` replaces it with one run a day |

## `[home]`

| Key | Default | Meaning |
| --- | --- | --- |
| `name` | `"Home"` | Name of the home geofence album |
| `lat`, `lon` | `37.3349`, `-122.0090` | Placeholder (Apple Park). Use a point near your home, not your door |
| `radius_km` | `25` | Photos inside this radius go to `Places · Home` |

## `[[geofences]]`

Repeat the table for each named place. A photo inside several geofences joins each of them, nearest centre first.

| Key | Required | Meaning |
| --- | --- | --- |
| `name` | yes | Album label, rendered through `templates.geofence` |
| `lat`, `lon` | yes | Centre, WGS84 degrees |
| `radius_m` | no, `300` | Radius in metres |

## `[albums]`

| Key | Default | Album produced |
| --- | --- | --- |
| `by_country` | `true` | `Places · France` |
| `by_city` | `true` | `Places · France · Paris` |
| `by_geofence` | `true` | `Places · Home`, `Places · Golden Gate Park` |
| `by_year` | `true` | `Timeline · 2026` |
| `by_month` | `true` | `Timeline · 2026-05` |
| `trips` | `true` | `Trip · Paris · 2026-05` |

### `[albums.templates]`

Python format strings. Available fields are listed per template. Names are normalised (Unicode NFC, collapsed spaces, `/` and `:` replaced with `-`, at most 120 characters), so the same input always yields the same album.

| Key | Fields | Default |
| --- | --- | --- |
| `country` | `country` | `Places · {country}` |
| `city` | `country`, `city` | `Places · {country} · {city}` |
| `geofence` | `name` | `Places · {name}` |
| `year` | `year`, `month` | `Timeline · {year}` |
| `month` | `year`, `month` | `Timeline · {year}-{month:02d}` |
| `trip` | `city`, `year`, `month` | `Trip · {city} · {year}-{month:02d}` |

## `[trips]`

| Key | Default | Meaning |
| --- | --- | --- |
| `min_distance_km` | `100` | A photo farther than this from home is "away" |
| `max_gap_days` | `1` | Days without away photos a trip may skip. A day with photos at home always ends a trip |
| `min_photos` | `5` | Smaller clusters are a day out, not a trip |
| `lookback_days` | `14` | How far before the last run `--since auto` re-reads, for trip context and late metadata |

## `[favourites]`

| Key | Default | Meaning |
| --- | --- | --- |
| `enabled` | `true` | Turn suggestions off entirely |
| `album` | `"Suggested favourites"` | Album that receives suggestions |
| `add_keyword` | `false` | Also add a keyword to suggested photos (opt-in, it writes photo metadata) |
| `keyword` | `"photosorg:suggested"` | The keyword |
| `top_n_per_event` | `2` | Suggestions per day or per event |
| `group_by` | `"day"` | `"day"`, or `"event"` to judge a whole trip as one |
| `min_score` | `0.65` | Nothing below this is suggested, even on a day with few photos |
| `near_duplicate_seconds` | `3.0` | Shots this close in time may be near-duplicates |
| `near_duplicate_score_delta` | `0.08` | Largest score difference for two close shots to count as near-duplicates |
| `skip_existing_favourites` | `true` | Photos you already hearted are not suggested again |
| `settle_hours` | `6` | Hours after midnight before a day is judged, so late syncs make it in |

`[favourites.weights]` and `[favourites.penalties]` are described in [scoring.md](scoring.md). Weights must add up to 1.0.
