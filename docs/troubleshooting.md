# Troubleshooting

Start with a plan. It reads the library, changes nothing, and shows the decision behind every photo.

```bash
photosorg plan --explain --limit 20
```

## Symptoms

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `osascript failed (1): ... Not authorized to send Apple events to Photos. (-1743)` | Automation permission missing, often because the first run came from launchd | Run `photosorg run` once from Terminal and accept the prompt. For the LaunchAgent, approve the Python binary under Privacy and Security, Automation |
| osxphotos cannot open the library, or reports a permission error | The running app lacks Full Disk Access to `~/Pictures` | Grant Full Disk Access to Terminal (or the agent's Python), then retry |
| `osxphotos is not installed` | The `macos` extra was not installed | `python -m pip install -e ".[macos]"` |
| A new photo has timeline albums but no place albums | Photos had not reverse geocoded it yet | Nothing. A later run inside `trips.lookback_days` adds the place albums |
| A photo from last month never got filed | It synced after the lookback window, or the library was restored | `photosorg run --since all` reconciles the whole library; it only adds what is missing |
| `album ...: N photos not reachable in Photos, skipped` (or `-1728`, `No se puede acceder al objeto`) | Photos cannot script that item: an iCloud Shared Library photo, or one not synced yet | Nothing breaks: the rest of the batch is filed. A later `run --since all` retries the skipped ones |
| Nothing is suggested for today | Days are judged only once they are over, plus `settle_hours` | Wait, or lower `settle_hours` |
| The agent is installed but never runs | It was not bootstrapped, or the plist was edited by hand | `photosorg install-agent` again; check `launchctl print gui/$(id -u)/io.github.marlyngiselle.photosorg` |
| `unknown key 'config.albums.by_planet'` | Typo in `config.toml` | Fix the key; see [configuration.md](configuration.md) |

## Logs

```bash
tail -n 50 ~/Library/Logs/photosorg/photosorg.log ~/Library/Logs/photosorg/photosorg.err.log
```

## Undo a run

```bash
photosorg stats
photosorg undo --run 20260620T190000Z-a1b2c3 --dry-run
photosorg undo --run 20260620T190000Z-a1b2c3
```

Undo removes only the memberships that run recorded. Albums the run created and that end up empty are deleted; deleting an album never deletes its photos.

The Photos scripting dictionary has no "remove from album" command, so removing some photos from an album that keeps others rebuilds it. A new album with the same name and the remaining photos is created in the same folder, then the old one is deleted. Anything you added to that album by hand is kept.

## Start over

```bash
photosorg uninstall-agent
rm ~/Library/Application\ Support/photosorg/state.sqlite3
```

Then delete the "Smart Organizer" folder in Photos. The next run rebuilds everything from scratch.
