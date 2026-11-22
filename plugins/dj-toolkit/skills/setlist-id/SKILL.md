---
name: setlist-id
description: Identify every track in a DJ set from a SoundCloud or YouTube link (or a local recording) - timestamps, exact version/remix, label, and streaming links - using free Shazam fingerprinting. Claude installs and runs it, or builds the double-click "Setlist ID" app for non-technical friends. Use when the user types /setlist-id, shares a DJ set / mix / boiler room / radio show link and asks "what tracks are in this", wants a tracklist, wants to ID a song from a set, or wants to download the tracks from a set they heard.
---

# Setlist ID

Give it a DJ set and it produces a tracklist with timestamps, the exact version, label and links. It's free: no accounts, paid APIs or AI services. The code is in `app/`:
- `setlist_id.py`: the CLI and the engine.
- `app.py`: a small local web UI on 127.0.0.1, used by the friend app.

Both list their own dependencies, so `uv run` installs everything on first use (yt-dlp, shazamio, httpx, a bundled ffmpeg).

## Run it for the user

```bash
S=<this skill's base dir>/app
export SETLIST_ID_HOME=~/.claude/dj-toolkit/setlist-id   # cache: audio + Shazam progress (resumable)
export SETLIST_ID_OUT=<setlists_folder>                  # each set gets its own subfolder, named from the title
uv run --upgrade-package yt-dlp "$S/setlist_id.py" "<set URL or audio file>" --country <shazam_country> --open
```
- Read `setlists_folder` and `shazam_country` from `~/.claude/dj-toolkit/config.md`. Defaults are `~/Music/Setlists` and `US`.
- **Always set both env vars.** Without them, data is written inside the plugin folder, which is replaced on every plugin update.
- Strip playlist parameters from YouTube links (`&list=...`, `&index=...`) and keep only `watch?v=<id>`.
- **Run it in the background.** A 1-hour set takes about 12-18 minutes, because Shazam rate-limits to about 1 request every 3 s and backs off on HTTP 429. Progress is cached, so an interrupted run resumes. Don't start two scans at once: they share the rate limit and both slow down.
- Output in `--out`: `tracklist.html` (the report, which `--open` opens), `tracklist.md` (for pasting into descriptions or notes) and `tracklist.json` (for Claude).
- Useful flags:
  - `--start 1:00:00 --end 1:30:00` scans part of the set.
  - `--step 20` catches quick cuts.
  - `--thorough` checks every step with no skipping.
  - `--keep-audio` keeps the audio for re-scans.
  - `--no-links` skips the link lookup.
  - Spotify exact links need `SPOTIFY_CLIENT_ID`/`SPOTIFY_CLIENT_SECRET` in the env (a free developer app). Without them it gives search links.

## After the scan
Read `tracklist.json` and give a short summary: the numbered tracklist with times, "possible" tracks (heard once, so they may be wrong), and ID gaps (unidentified, often unreleased). Then offer the natural next step:
- **"Want these tracks?"** → pass the identified tracks (exact version names) to **get-songs**. Skip "possible" tracks unless the user picks them.
- Paste-ready tracklist text for a SoundCloud or YouTube description.

## How it works (for answering questions)
1. yt-dlp downloads the audio and converts it to 16 kHz mono (cached).
2. 12 s clips every 30 s go to Shazam. After 3 matching answers in a row it skips ahead up to 120 s, and it backfills when the answer changes. Layered blends are always sampled densely.
3. Consecutive hits are merged into tracks. The release with the most hits wins (the rest appear as "also matched as"). A single-hit track is shown dimmed as "possible".
4. If the description or chapters have a tracklist, it cross-checks against it ("✓ in description") and lists tracks the scan missed.
5. Links come from the ISRC: Apple Music and Deezer always, Spotify with keys, a song.link page for every platform, and search links for YouTube, SoundCloud, Tidal, Beatport, Traxsource and Bandcamp.

Limits:
- Unreleased IDs aren't in any database.
- Heavy pitch or tempo changes and long blends reduce matches; a lower `--step` helps.
- Extended and original mixes share audio, so check "also matched as".
- shazamio is an unofficial client. If Shazam breaks it, `uv run --upgrade-package shazamio ...` usually fixes it.

## Build the double-click app for a friend
For people who'll never open a terminal: `bash <skill>/scripts/build_app.sh [output dir]` makes `Setlist ID.zip` (default `~/Desktop`). It contains:
- `Setlist ID.command` (Mac) and `Setlist ID.bat` (Windows). On first run these download uv, Python and the dependencies into the app folder, then open a page in the browser.
- `How to use.txt`, with plain-language steps including the "Open Anyway" / "Run anyway" first-launch warnings.

The friend unzips it, double-clicks, pastes a link and presses Go. Nothing gets installed system-wide, and deleting the folder removes everything.
