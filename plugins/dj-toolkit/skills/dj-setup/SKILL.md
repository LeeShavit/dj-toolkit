---
name: dj-setup
description: One-time setup for the DJ toolkit - learns the user's DJ software, library folders, protected folders, genres, download sources and preferences, installs the shared runtime (uv, ffmpeg), and writes ~/.claude/dj-toolkit/config.md that every DJ toolkit skill reads. Use when the user types /dj-setup, installs the dj-toolkit plugin, wants to change their DJ settings, or any dj-toolkit skill finds no config.
---

# DJ toolkit setup

Every dj-toolkit skill (get-songs, setlist-id, organize-library, audio-quality, upgrade-to-extended, rekordbox-tools, dj-troubleshooting) reads one file: **`~/.claude/dj-toolkit/config.md`**. This skill writes it. If a skill needs a setting that isn't there, it asks just that question and adds the answer here. It doesn't rerun the whole setup.

```
~/.claude/dj-toolkit/
├── config.md       # this user's settings (template: templates/config.md)
├── platforms.md    # download sources (get-songs)
├── secrets/        # keys and sessions, chmod 700
├── runs/           # reports from downloads, scans and upgrades
└── backups/        # rekordbox DB and file backups made by the tools
```

## Flow

### 1. Look before asking (silently)
- OS and CPU: `uname -sm`.
- DJ software: on macOS look in `/Applications` for rekordbox, Serato DJ, Traktor, VirtualDJ and djay; on Windows look in Program Files. The rekordbox DB is at `~/Library/Pioneer/rekordbox/master.db` (macOS) or `%APPDATA%\Pioneer\rekordbox\master.db`.
- Music folders: folders under `~/Music` and `~/Downloads` with many audio files. Count by folder with `find -maxdepth 3`.
- Tools: `uv`, `ffmpeg`/`ffprobe`, `python3`. Download apps such as OfflineDJ and Telegram.

### 2. Install the shared runtime
All toolkit scripts are self-contained Python scripts that list their own dependencies, and they run with **uv**. That means no virtualenvs and no `pip install`, and the same commands work on macOS, Windows and Linux.
- `bash <skill>/scripts/ensure_tools.sh` installs uv (from astral.sh) if missing and reports ffmpeg. On Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`, plus `winget install ffmpeg`.
- If ffmpeg is missing on macOS, offer `brew install ffmpeg`. If Homebrew isn't there either, the scripts fall back to the `imageio-ffmpeg` binary that uv installs. Mention that it's slower.

### 3. Interview (AskUserQuestion, grouped, multiple choice)
Confirm what step 1 found rather than asking blind.
1. **About you**: what you use music for (club DJ / events DJ / listening / producing), DJ software and version, controller (optional).
2. **Library**: where your DJ music lives. **Which folders must never be changed?** Explain why this matters: a finished, carefully curated library, or one the DJ software has analysed with cue points, should be read-only for every tool. Then: genre folders (offer the ones found on disk, or a starter set), and where new batches should go.
3. **Downloads**: run `get-songs/references/setup.md` steps 2-5 (version, quality, buying, sources, order).
4. Setlist folder and Shazam country, only if they want setlist-id.

### 4. Write the config
`mkdir -p ~/.claude/dj-toolkit/{secrets,runs,backups} && chmod 700 ~/.claude/dj-toolkit/secrets`, then fill `templates/config.md` → `~/.claude/dj-toolkit/config.md`. Show a short summary and list what they can do now:

```
/get-songs <songs>        download in the best version
/setlist-id <set link>    tracklist of a DJ set
/organize-library         sort + tag a new batch for your DJ software
/audio-quality <folder>   find fake lossless files
/upgrade-to-extended      swap radio edits for extended versions
/rekordbox-tools          repoint playlists, BPM/grid checks
/dj-troubleshooting       no sound, stuck analysis, ...
```

Re-running setup prefills from the existing config and asks only about changes.

## Rules every toolkit skill follows
- `protected_folders` are read-only for every tool, every time. Before any write, check paths with a trailing separator (`path.startswith(folder + "/")`). A bare prefix check treats `DJ Library 9.11` as inside `DJ Library`. This bug happened once and left 18 files unprocessed.
- Delete means move to Trash, and only after the user says so.
- Back up before any DJ-software database write, and test on a copy first.
- Show a review (page or table) and get approval before changing music files.
- The user may be changing files at the same time. Re-check the disk before moving anything, and reconcile counts at the end.
