---
name: platform-streamrip
description: Download lossless tracks from the user's own Qobuz, Tidal, Deezer or SoundCloud subscription using the streamrip CLI (`rip`). Use when get-songs routes tracks to a streaming subscription, or the user says they have Qobuz / Tidal / Deezer and wants tracks downloaded from it.
---

# Streaming subscriptions (streamrip)

streamrip is an open-source CLI that downloads from Qobuz, Tidal, Deezer and SoundCloud using the user's **own paid account**. Lossless (up to 24-bit on Qobuz/Tidal) needs a matching plan. Catalog coverage is like any streaming service: very good for official releases, including many "Extended Mix" releases from dance labels. It's weak for bootlegs and DJ-pool edits.

## Setup (one time)
1. Install: `pipx install streamrip`, or `python3 -m pip install --user streamrip` (needs Python 3.10+). Install `ffmpeg` too (brew/apt/winget).
2. Configure: `rip config open` opens the config file. Fill in the login for the user's service. **The user types credentials themselves**; ask them to edit the file, and don't take passwords in chat. Notes per service:
   - Qobuz: email + password, or a token. Set `quality` (1=320, 2=16/44, 3=24/96, 4=24/192).
   - Tidal: `rip` starts a device login link the first time. The user opens it and approves.
   - Deezer: needs the `arl` cookie from the user's logged-in browser session (deezer.com → DevTools → Cookies → `arl`).
3. Set the download folder in the config (`downloads.folder`) to get-songs' `download_folder`, or a subfolder of it.
4. Test with one popular track.

## Download tracks
```bash
rip search qobuz track "Artist Title Extended Mix"     # interactive picker; check `rip search --help` for a first-result flag
rip url "https://open.qobuz.com/track/123456"            # a direct link is best: no ambiguity
rip id qobuz track 123456
rip file links.txt                                       # many URLs, one per line
```
For lists: search the web or the service for each track's URL first, matching the exact version and length, then pass the URLs to `rip file`. This avoids the wrong-version problem. Run `rip --help` to confirm flags, since they change between versions.

## Reading results
Files land in the configured folder, organised as Artist/Album by default. Check them with `check_audio.py`. Errors like "not streamable" mean the track is region-locked or unavailable on that plan.

## Notes
Downloading from a subscription for offline use may be against the service's terms in some countries. That's the user's call; mention it once during setup.
