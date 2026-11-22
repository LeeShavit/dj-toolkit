---
name: platform-soulseek
description: Download songs from Soulseek (free peer-to-peer network, lots of FLAC/320 and DJ extended mixes) using the sldl / Sockseek command-line tool - takes whole lists, CSVs or playlists. Available to everyone, no subscription. Use when get-songs routes tracks to Soulseek, as the free fallback for tracks other sources missed, or when the user asks to search or download from Soulseek / slsk.
---

# Soulseek (sldl / Sockseek)

Soulseek is a free file-sharing network where people share their music folders. It has great coverage of club music, including extended mixes from DJ pools. Coverage is never guaranteed, though, because a track is only available if someone online is sharing it. **sldl** (the project was renamed Sockseek; the binary is `sockseek`, and we link it as `sldl`) searches and downloads whole lists from the command line.

Real-world result (35-track DJ list): ~55% found, all FLAC/320, but 3 of 20 were the wrong version. **Always verify versions.**

## Setup (one time)
1. Install: `bash <skill>/scripts/install_sldl.sh`. It fetches the latest release for this OS/CPU from github.com/fiso64/sockseek into `~/.local/share/sockseek` and links `~/.local/bin/sldl`. On Windows, download the `win-x64.zip` from the releases page instead.
2. Account: Soulseek creates an account automatically the first time a new username logs in. Ask the user whether they have one; if not, offer to create one with a random name and a strong password.
3. Write `~/.config/sockseek/sockseek.conf` (chmod 600):
   ```
   username = <user>
   password = <pass>
   format = flac,mp3,wav,aiff
   pref-format = flac
   min-bitrate = 320
   ```
   If the user doesn't want lossy at all: `format = flac,wav,aiff`.

## Download tracks
Give it a CSV with `Artist,Title` columns. It matches better than a plain list, where "A - B" is parsed as an album:
```bash
python3 - <<'EOF'
import csv; rows=[l.strip() for l in open("list.txt") if " - " in l]
w=csv.writer(open("list.csv","w",newline="")); w.writerow(["Artist","Title"])
[w.writerow(r.split(" - ",1)) for r in rows]
EOF
sldl list.csv -o "<download_folder>/soulseek" --no-listen > sldl.log 2>&1   # run in background
```
- Single track: `sldl "artist=Darude, title=Sandstorm (Extended Mix)" -o <dir>`
- Retry only the failures: rerun the same command. It skips what was downloaded (`--skip-not-found` also skips tracks that weren't found last time).
- Results: the last line `Completed: X succeeded, Y failed`. Per track: `SongJob: succeeded|failed [reason]: <track>`.
- Other inputs it accepts: Spotify playlist URLs (need the user's own Spotify developer app plus Premium), YouTube playlists, Bandcamp URLs. Run `sldl --help input`.
- `sldl daemon` runs a local HTTP API (port 5030), and `--remote` uses it.

## Reading failures
- `No search results`: nobody online shares it right now. Try again later, or relax the search: drop `(Extended Mix)` and filter by version yourself, or try `--desperate`.
- `Transfer rejected: Too many files` / `stale`: the track was found, but the sharer refused or stalled. Very common for brand-new accounts that share nothing. Fixes: retry later; share a folder of music, since many users only send to people who share (set `shared-folders`/`shared-files` honestly, or use a full client like Nicotine+); leave the run going longer.
- A wrong version gets downloaded: the search matched loosely. Check every file against the target with `check_audio.py` and the version rules, and move mismatches to `_rejected/`.

## Etiquette and safety
Be a good peer: don't hammer searches (sldl's default rate limits avoid 30-minute bans). Files come from strangers: run only audio through tools, and never open other file types it downloads.
