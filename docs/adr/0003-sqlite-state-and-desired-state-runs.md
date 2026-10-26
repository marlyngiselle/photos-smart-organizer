# ADR 0003. SQLite state and desired-state runs

Accepted in October 2026.

## Context

The tool runs every 30 minutes for years. It must not create duplicate albums, must not re-add photos, must survive Photos quitting halfway, and must be able to undo any single run.

Photos itself could be asked what each album contains, but that is slow through scripting and says nothing about which run added what.

## Decision

A local SQLite file (`~/Library/Application Support/photosorg/state.sqlite3`, stdlib `sqlite3`, no ORM) records runs, memberships with the run id that created them, albums the tool created, trips, and the days already judged for suggestions.

Each run computes the desired memberships for its window and writes only the difference from the recorded ones, like a plan and apply.

## Consequences

1. Re-runs are no-ops and cost zero Apple events.
2. `undo --run <id>` is exact, including deleting albums that run created and that would be left empty.
3. Partial failures are safe. Additions are recorded as they land, the run is marked failed, and the high-water mark does not move.
4. If someone removes a photo from an album by hand, the state still believes it is there and will not re-add it. That is deliberate. Manual curation wins.
5. Deleting the state file is a reset of memory, not of Photos. Existing albums are found by name and reused, never duplicated. For a clean slate, delete the "Smart Organizer" folder in Photos as well.
