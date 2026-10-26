# ADR 0002. osxphotos for reads, JXA through osascript for writes

Accepted in October 2026.

## Context

There are two ways into a Photos library. Photos' scripting interface (AppleScript or JXA) can create albums and add items but exposes very little metadata, and it is slow per item. The library database holds everything Photos computed (places, scores, bursts, duplicates, faces) and the open source osxphotos project reads it read-only and is widely used.

PhotoKit would be the official API, but it needs a signed app bundle with a usage description, which is heavy for a personal automation.

## Decision

1. Read with osxphotos, behind the `PhotoReader` protocol. The import is lazy and the dependency is an optional extra (`photosorg[macos]`), so the core and the test suite run anywhere, including Linux CI.
2. Write with a single JXA script (`jxa/photos_album.js`) called through `/usr/bin/osascript`, behind the `PhotoWriter` protocol. It does six things: ensure an album, add, remove, delete an empty album, add a keyword, remove a keyword.

photoscript (the AppleScript bridge osxphotos itself uses) was considered for writes. JXA through osascript was chosen because it adds no dependency, the script can be syntax-checked in CI with `osacompile`, and every call is a separate short process that cannot leave Photos in a half-scripted state.

## Consequences

1. Reads are fast and rich; writes are batched per album in chunks of 200.
2. osxphotos follows Photos database changes across macOS releases. A macOS upgrade can require an osxphotos upgrade before reads work again.
3. The Photos dictionary has no "remove from album" command, so undo rebuilds an album when it must keep other photos. See [troubleshooting](../troubleshooting.md).
