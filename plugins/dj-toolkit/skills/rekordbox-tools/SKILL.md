---
name: rekordbox-tools
description: Work directly with the rekordbox 6/7 database (via pyrekordbox) - collection status and missing files, repoint tracks/playlists to new or upgraded files without rebuilding playlists (keeps cues where audio is identical), merge duplicate entries, and BPM / beatgrid triage (near-whole BPMs that drift vs real decimals). Always backs up and tests on a copy first. Use when the user types /rekordbox-tools, asks "does rekordbox have a CLI / can you do it for me", wants playlists to point at new files, has missing tracks after moving files, has duplicate collection entries, or asks about wrong BPMs or drifting grids.
---

# rekordbox tools

`scripts/rb.py` uses **pyrekordbox**, an open-source library that reads and writes rekordbox's encrypted `master.db`. Run it with `uv run <skill>/scripts/rb.py <command>`. It handles its own dependencies, including SQLCipher.

**Read** commands work while rekordbox is open. **Write** commands need rekordbox *and its background agent* fully quit. pyrekordbox refuses to commit otherwise, even on a test copy.

## Commands
| Command | What it does |
|---|---|
| `status` | Track count, missing files, tracks needing analysis, playlists, where tracks live |
| `missing` | Lists tracks whose file is gone (they show "!" in rekordbox) |
| `bpm [--folder X]` | BPM triage (see below) |
| `map --old-root A --new-root B -o map.csv` | Proposes old → new file pairs for tracks under A (same genre subfolder, same core artist and title) |
| `plan --map map.csv -o plan.csv` | Classifies each pair: **repoint** (identical audio: keeps cues and grid), **swap** (different audio: resets analysis and deletes cues), **merge** (two entries → one file, playlists combined), **skip** (new file shorter or missing) |
| `apply --plan plan.csv [--db COPY]` | Writes it. Backs up `master.db`, `-wal` and `-shm` to `~/.claude/dj-toolkit/backups/` first |

## Repointing playlists to new files (e.g. after upgrade-to-extended)
1. `status`, to see where the tracks live now.
2. `map`, then **review `map.csv` with the user**. Fuzzy matching is a starting point (it got 206 of 527 right on its own in a real run). A curated list beats it: upgrade-to-extended's matches, or the user's decisions. Ask about **different remixes**: in one run the user chose to skip 29 songs where the "new" file was a different remix.
3. `plan`, then show the counts and any "skip (new file shorter)" rows. **Only swap when the new file really is longer** (4 were rejected in a real run).
4. **Test on a copy.** Copy the raw files, since the DB is encrypted:
   `mkdir -p "$WORK/testdb" && cp ~/Library/Pioneer/rekordbox/master.db* "$WORK/testdb/"`
   then `rb.py apply --plan plan.csv --db "$WORK/testdb/master.db" --yes`, then `rb.py status --db "$WORK/testdb/master.db"`. Check the counts: tracks under the new root went up, missing files didn't, and playlist entries are unchanged (or down only by merges).
5. The user quits rekordbox fully. Then run `apply --plan plan.csv` on the live database. It refuses if rekordbox is running, and it asks for "yes" (pass `--yes` only after the user has approved in chat).
6. `status` again to verify. Then tell the user, in rekordbox: select the swapped tracks → **Reload Tag** → **Analyze Track**, and re-set hot cues on swapped tracks that had them. (`plan.csv` lists which tracks were swapped, and their cue points are gone.)

If the music folder is still changing (another session, a downloader, the user), wait until it has been stable for about 15 minutes and redo `map`. Matching against a moving folder caused a redo once.

## BPM / beatgrid triage
`rb.py bpm` reads the BPM rekordbox stored (`BPM/100`):
- **Near-whole** (within 0.05 of an integer, e.g. 127.99): the real tempo is the whole number, and the grid will drift over a long mix. Fix: set **Preferences → Analysis → Track Analysis Mode = Normal** (not Dynamic) and a BPM range that suits the genre (e.g. 128-175 for trance), then re-analyse. Or do it manually: Grid Edit → set the 1st beat → type the rounded BPM → lock.
- **Real decimals** (e.g. 141.85): common on vinyl and tape-era and live-played records. They're correct. Leave them, or mix those tracks with sync off.
Mixed In Key and Lexicon don't fix grids. Don't recommend paid tools for this.

## Missing files
`rb.py missing` lists them. If the files were moved, rekordbox's **File → Library → Display All Missing Files → Auto Relocate** (pointing at the new folder) usually fixes it. Or build a mapping and use `plan`/`apply` (repoint).

## Safety
- Always back up and test on a copy before any write.
- Never write while rekordbox runs.
- Never touch tracks in `protected_folders` beyond repointing *away* from them (and only when the user asked).
- Other DJ software: Serato stores data in `_Serato_` folders and file tags, Traktor in `collection.nml` (XML). Don't edit those with this tool. Explain the app's own relocate feature instead.
