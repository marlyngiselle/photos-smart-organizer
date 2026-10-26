# Privacy and permissions

photosorg runs entirely on your Mac. It has no network code, no telemetry and no cloud service. iCloud Photos moves your photos from iPhone to Mac; photosorg only works with what is already in the library.

## What it reads

| Data | Source | Used for |
| --- | --- | --- |
| UUID, capture date, date added | Photos database, via osxphotos | Identity, timeline albums, the `--since auto` window |
| GPS latitude and longitude | Photos database | Geofences, home distance, trips |
| Country and city names | Reverse geocoding Photos already did on device | Place albums |
| Face count, named people count | Photos database | Two scoring signals (counts only, never names) |
| Aesthetic scores (`overall`, `curation`, `sharply_focused_subject`, `well_framed_subject`) | Photos' on-device analysis | Scoring |
| Burst, duplicate, screenshot, hidden, favourite flags | Photos database | Exclusions and de-duplication |

It never reads image pixels, never exports a file and never copies the library.

## What it writes

| Where | What |
| --- | --- |
| Photos.app | Albums inside the folder "Smart Organizer", and photo membership in them |
| Photos.app, opt-in | The keyword `photosorg:suggested` when `favourites.add_keyword = true` |
| `~/Library/Application Support/photosorg/state.sqlite3` | Photo UUIDs, album names, run ids, trip names and dates |
| `~/Library/Logs/photosorg/` | Run logs (album names and counts) |
| `~/Library/LaunchAgents/io.github.marlyngiselle.photosorg.plist` | The schedule, if you install it |

It never edits a photo, never deletes a photo, never moves a photo out of an album it did not add it to, and never toggles the favourite heart. Suggestions go to an album precisely so that the decision stays yours.

The state DB stores no coordinates and no people names. Trip names do contain a city, because they are album names.

## macOS permissions you will see

| Prompt | Why | Granted to |
| --- | --- | --- |
| "Terminal wants access to control Photos" (Automation) | The writer sends Apple events to Photos to create albums and add photos | The app that runs `photosorg`: Terminal, iTerm, or the Python binary for the LaunchAgent |
| Full Disk Access (only if reads fail) | The Photos library lives under `~/Pictures`, which macOS protects. osxphotos reads its database directly | Same app as above |

Run `photosorg run` once from Terminal so the Automation prompt appears while you are watching. A background LaunchAgent cannot show a prompt, so a first run from launchd would fail with error -1743 instead.

## How to revoke

1. Stop the schedule.

   ```bash
   photosorg uninstall-agent
   ```

2. Revoke Automation in System Settings, Privacy and Security, Automation, then untick Photos under the app. From a shell, for Terminal:

   ```bash
   tccutil reset AppleEvents com.apple.Terminal
   ```

3. Revoke Full Disk Access in System Settings, Privacy and Security, Full Disk Access, or:

   ```bash
   tccutil reset SystemPolicyAllFiles com.apple.Terminal
   ```

4. Remove local state and logs.

   ```bash
   rm -rf ~/Library/Application\ Support/photosorg ~/Library/Logs/photosorg
   ```

Albums already created stay in Photos until you delete the "Smart Organizer" folder. Deleting an album or a folder in Photos never deletes the photos in it.
