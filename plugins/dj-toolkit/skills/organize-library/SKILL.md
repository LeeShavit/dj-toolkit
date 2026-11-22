---
name: organize-library
description: Organize a batch of DJ music (new downloads or a messy music folder) into genre folders, remove true duplicates by comparing audio, fill in all possible metadata (title, artist, label, year, ISRC, remixer, BPM, key, genre), clean junk tags, and prepare it for rekordbox (XML import) - with a review page before any file changes and protected folders never touched. Use when the user types /organize-library or /organize-dj, says they downloaded new music to sort, tag, clean up or add to rekordbox/Serato, or asks to organize their music library or fix metadata.
---

# Organize a DJ library batch

This is the repeatable flow for sorting, tagging and importing a batch of tracks. It was built and refined on a real 565-song rekordbox library. Read `~/.claude/dj-toolkit/config.md` first for `music_root`, `library_folders`, `protected_folders`, `genres`, `new_batches_go_to`, `dj_software`, `one_copy_per_song` and `delete_mode`. If there's no config, run `dj-setup` (or ask just what this flow needs).

## Hard rules
1. **`protected_folders` are read-only.** No tags, moves, renames or deletes, ever. Read them only, to spot songs the user already owns. Match paths with a trailing separator. If the user asks to change a protected folder, confirm they mean to lift the rule first.
2. New music goes to a **new folder** (`new_batches_go_to`, default `~/Music/DJ New <YYYY-MM>/<Genre>/`). Ask for the name first. A finished library stays finished.
3. **One copy of each song**, but a radio edit and an extended mix, or two different remixes, are *different songs*. Keep both.
4. Delete = move to Trash, only after the user says so. Never `rm`.
5. No music file changes until the user approves the review page, and the DJ software must be quit first (`pgrep -x rekordbox`).
6. Keep filenames unchanged unless two files truly collide.

## Setup
Scripts are in `scripts/` and run with `uv run` (they list their own deps). Work files go in the session scratchpad:
```bash
export WORK=<scratchpad>/organize MUSIC_ROOT=<music_root> SCAN_DIR=<folder with the new batch>
export PROTECTED="<protected folder 1>:<protected folder 2>"   # absolute or relative to MUSIC_ROOT; ';' on Windows
mkdir -p "$WORK"
```
`scan.py` skips protected folders, and `apply.py` refuses any plan that touches them. `reference/` holds the scripts from a real run, with hardcoded paths and track IDs. Use them as models and adapt them; don't run them as they are.

## Flow

### 1. Back up
- DJ software data:
  - rekordbox: `cp -r ~/Library/Pioneer/rekordbox ~/.claude/dj-toolkit/backups/rekordbox_$(date +%Y%m%d_%H%M%S)` (Windows: `%APPDATA%\Pioneer\rekordbox`).
  - Serato: the `_Serato_` folder in the music root.
  - Compare with `diff -rq`.
- The batch: `cp -cR "<folder>" "$BACKUP/"` (an APFS clone that takes almost no space). **No trailing slash on the source**: on macOS, `cp -R dir/` copies the *contents* and flattens folders, silently overwriting same-named files. Compare per-folder file counts.

### 2. DJ software export (rekordbox)
Ask the user to run **File → Export Collection in xml format** to `~/Documents/rekordbox.xml`. Check for a recent existing one first. Report how many tracks are in the collection, how many have cue points, and which new files are already in it. (Serato/Traktor: skip XML and organize files only; their crates or collections are updated in the app.)

### 3. Scan, then find duplicates
- `uv run scripts/scan.py "$WORK/scan.json"` reads tags, quality and tag gaps.
- Compare **audio, not bytes or filenames**. Files with identical audio can differ in size because of their tags. Use the FLAC STREAMINFO MD5, or for any format an MD5 of the first 60 s decoded by ffmpeg (`-f s16le -ac 2 -ar 44100`). See `reference/dupes_example.py`.
- Compare the batch against itself **and against `library_folders`**. If a song is already in the library, the new copy is the one that goes.
- Same title, key and BPM, and length within about 2 s, means the same song from a different master. Offer to keep one: the higher quality file, or the one the DJ software already uses.
- Flag files with AUDIOCHECK comments marked FAKE, or run the **audio-quality** skill on the batch.

### 4. Online lookup
`uv run scripts/enrich.py > "$WORK/enrich.log"` in the background. It queries Deezer with artist and title only, read-only. Confidence: `high` means the artist matches, title similarity is at least .85 and the duration is within 3 s; `medium` means at least .6 and within 8 s. Don't use `low`/`none` matches.

### 5. BPM and key estimates
`uv run scripts/analyze_audio.py > "$WORK/audio.log"` in the background (essentia, local). It only runs on tracks missing BPM or key. Mark these as estimates, since the DJ software replaces them when it analyses.

### 6. Assign genres
Use `genres` from config. These are the folder names, with `&` written as `and` on disk.
- Read every track and make an explicit decision. **Don't use a catch-all default genre.** A "Tech House by default" rule once put 8 classic house songs in Tech House.
- Use the release era as well as the style: a re-release date doesn't make an old track recent.
- Flag obscure artists as "check genre" rather than guessing silently. You haven't listened to anything, so say so.
- A track that fits several genres lives in one folder and joins several playlists.

### 7. Review page
Build `~/Documents/library_review.html` from `scripts/review.tpl.html` (see the end of `reference/plan_example.py`), `open` it, and summarise genre counts, files to check, duplicates and tag changes. Wait for approval. Apply corrections straight away and rebuild the page.

### 8. Apply (after approval, DJ software quit)
Test on a sandbox copy of one FLAC, one MP3 and one WAV: `uv run scripts/apply.py --test <dir>`. Then `uv run scripts/apply.py` (it reads `$WORK/plan.json`). Preflight confirms nothing overwrites an existing file and nothing is in a protected folder.

Tag rules:
- Set genre to the DJ genre. Fill title, artist, album, year, label, ISRC, barcode, remixer (from the title), BPM and key.
- Only fill gaps, apart from genre and the cleanups below. Keep existing artwork.
- Clean labels of `℗ 2020` prefixes and "distributed by" text. Normalise keys to musical notation (rekordbox can show Camelot).
- Remove downloader ads from comments (e.g. "Downloaded with OfflineDJ"). Keep `AUDIOCHECK` text.

### 9. Verify and build the import file
- Compare every file's audio against the backup, check its genre tag, and remove source folders that are now empty.
- rekordbox: base `~/Documents/rekordbox_organized.xml` on the fresh export, adding the new tracks plus a playlist folder for this batch (see `reference/verify_xml_example.py`). **Leave entries pointing into protected folders as they are.** Re-read the XML: no missing track locations and no dangling playlist keys. Report tracks that were already missing.

### 10. Hand off (rekordbox)
Give only the steps needed. If tracks that were already in rekordbox moved, run Auto Relocate first (**File → Library → Display All Missing Files**), or the import may add them twice. Then:
1. **Preferences → Advanced → Database → rekordbox xml**: set Imported Library to the XML.
2. In the sidebar under **rekordbox xml**, right-click the new playlist folder → **Import to Collection**.
3. In Collection, **Reload Tag** on tracks that were already there, then **Analyze Track**.

Menu names may differ between versions, and the import can't be tested from here, so say so. Say where the backups are, and that they can be deleted once rekordbox looks right. If analysis then hangs, see **dj-troubleshooting** (Cloud Analysis).

## Before saying it's done
If the DJ software was opened during the work, or a count is off, reconcile the plan against the disk before any more moves. The user may be changing things at the same time.
