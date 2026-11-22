# dj-toolkit 🎧

A Claude Code plugin that collects a working DJ's know-how into skills Claude runs for you: downloading songs in the right version, identifying tracks in sets, organizing and tagging your library, catching fake lossless files, upgrading radio edits to extended mixes, and fixing rekordbox.

## Install

**Claude Desktop** (Mac or Windows, any paid Claude plan):
1. Open the **Code** tab and start a **local** session (not cloud). Any folder works.
2. Paste these two lines, one at a time:
   ```
   /plugin marketplace add LeeShavit/dj-toolkit
   /plugin install dj-toolkit@dj-toolkit
   ```
   Choose **user** scope if asked. You can also click **+** → **Plugins** (or **Add plugins**) and install from there once the marketplace is added.
3. Start a **new** session and type `/dj-setup`. It may be listed as `/dj-toolkit:dj-setup`.

**Terminal** (Claude Code CLI): `claude plugin marketplace add LeeShavit/dj-toolkit && claude plugin install dj-toolkit@dj-toolkit`, then `/dj-setup` in a new session. Desktop and the CLI share installed plugins.

**Updates:** `/plugin marketplace update dj-toolkit`, then start a new session.

Cowork isn't supported yet. The tools run scripts on your own music folders, which needs a local Code session.
`/dj-setup` asks about 5 minutes of questions: your DJ software, library folders, **folders that must never be touched**, genres, download sources and preferences. Then it installs the small runtime (`uv` + `ffmpeg`). Every tool reads that one config.

## The tools

| Command | What it does |
|---|---|
| `/get-songs <songs, file or playlist link>` | Downloads in the best version for mixing (extended/club) from **your** sources, in your order: Offline DJ (via its Telegram bot), Qobuz/Tidal/Deezer (streamrip), Soulseek (sldl), Beatport/Bandcamp carts (you pay yourself), YouTube/SoundCloud as a labelled last resort. Skips what you already have, checks every file, and **learns new platforms** as new skills. |
| `/setlist-id <set link>` | Tracklist of any SoundCloud/YouTube DJ set: timestamps, exact remix, label, links. Free (Shazam fingerprinting, no accounts). Can also build a double-click **Setlist ID** app for friends who never open a terminal. |
| `/organize-library` | Sorts a batch into genre folders, removes true duplicates by comparing audio, fills every tag it can (Deezer lookups, local BPM/key estimates), cleans junk tags, shows a review page, then builds a rekordbox XML import. Never touches your protected folders. |
| `/audio-quality <folder>` | Finds FLAC/WAV files made from MP3s, and "320s" upscaled from 128, by spotting the encoder's frequency cliff. Report, optional comment tags for sorting in your DJ software, and re-download of fakes. |
| `/upgrade-to-extended` | Finds the extended version of every song in your library (same remixer, verified length), downloads them via get-songs, catches "extended" files that are really radio edits, and picks the best version to mix (clean beat intro/outro, no fades). |
| `/rekordbox-tools` | rekordbox database tools: status and missing files, **repoint playlists to new files** without rebuilding them (keeps cues when the audio is identical), merge duplicates, BPM/grid triage. Backs up and tests on a copy first. |
| `/dj-troubleshooting` | Proven fixes: no sound from the controller, quiet headphones, rekordbox analysis stuck (Cloud Analysis), drifting grids, missing tracks. |

## Your data and safety
- Everything personal stays on your computer in `~/.claude/dj-toolkit/`: config, platform notes, reports, backups, and `secrets/` (readable only by you).
- **Protected folders** you name in setup are read-only for every tool.
- Nothing is deleted: removed files go to the Trash, and only when you say so.
- Music files only change after you approve a review. DJ-software databases are backed up and tested on a copy first.
- get-songs never completes a purchase and never bypasses DRM or paywalls.

## Requirements
Claude Desktop (Code tab) or Claude Code, on a paid plan · macOS or Windows (Linux works for most tools) · `uv` and `ffmpeg` (installed by `/dj-setup`) · Claude in Chrome for the Beatport/Bandcamp cart and Beatport version lookups.

## Fair use
You're responsible for following copyright law and each service's terms where you live. Support the artists you play. 🙏
