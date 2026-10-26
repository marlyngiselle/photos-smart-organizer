# ADR 0001. Suggest into an album, never toggle the favourite heart

Accepted in October 2026.

## Context

The goal is to surface the best photos of each day. Photos has a native favourite flag (the heart), and it can be set through scripting. Setting it would be the most visible result.

## Decision

Suggestions go to a regular album, "Suggested favourites", inside the tool's folder. The favourite flag is never written. An optional keyword (`photosorg:suggested`) is available behind `favourites.add_keyword`, off by default.

## Consequences

1. The heart keeps meaning "I chose this". It syncs to every device and feeds Memories and widgets, so a wrong automatic heart would spread.
2. A suggestion is reversible with no trace. Undo removes album membership; nothing about the photo itself changed.
3. Accepting a suggestion is one tap in the album, which is the human in the loop we want.
4. The writer's contract (`PhotoWriter`) has no method that touches the flag, and a test asserts the JXA bridge contains no favourite assignment.
