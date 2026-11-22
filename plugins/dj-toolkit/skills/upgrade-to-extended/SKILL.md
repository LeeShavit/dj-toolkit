---
name: upgrade-to-extended
description: Upgrade a DJ library from radio edits to extended / club versions - scans every track, finds the extended mix (same remixer, verified length) via Deezer, iTunes and Beatport, builds a download list for get-songs, verifies what arrives by actual length, then picks the best version of each song for mixing (clean beat intro/outro, no fades, real quality) and can repoint rekordbox playlists to the new files. Use when the user types /upgrade-to-extended, says their library is full of radio edits or short versions, downloaded a Spotify playlist and got radio edits, wants extended versions of all their songs, or asks which version of a song is better to mix.
---

# Upgrade a library to extended versions

Streaming-sourced libraries are mostly radio edits (a real one had a median length of 3:25). DJs want the extended or club version: a clean beat at the start and end to mix on. This is the flow that upgraded a 565-song library. It **never modifies the source library**. Upgraded files go into a new folder with the same genre structure.

Read `~/.claude/dj-toolkit/config.md` first. The library comes from `library_folders`, and `protected_folders` covers the old library if the user wants it kept. Scripts run with `uv run` (they list their own dependencies) and write to a work folder in the session scratchpad. Copy finished reports to `<new library>/Reports/`.

## 1. Set up the target
Ask for the new folder name. Suggest `<library> Extended`, or the date (one user used "DJ Library 9.11"). Create the same genre subfolders. Tracks that are already extended get **copied**, never moved, so the old library stays whole.

## 2. Find the extended versions
```bash
uv run <skill>/scripts/find_extended.py --library "<library>" --out "$WORK"
```
Run it in the background. It takes about 1-2 s per track and caches its lookups in `http_cache.json`, so reruns are fast.
- **Already extended**: 5:00 or longer, or labelled extended/club/12"/original mix and 4:00 or longer. Copy these into the new library.
- **found**: a high-confidence match → `extended-list.txt`.
- **review**: plausible but unsure → `extended-review.txt`. Go through these with the user or check them on Beatport (step 3).
- **none**: nothing found.

Matching rules (in the script; explain them when asked):
- Title similarity at least .85, and the artist must match.
- The length must be at least max(current + 45 s, 4:00).
- Reject: radio, instrumental, live, "(Mixed)" / DJ-mix / megamix / continuous, sped up or slowed, and "edit" unless it's extended or club. Reject dubs unless the original is a dub.
- **A remix's extended version must be by the same remixer.** A different remix is a different song. The main artist's own name in a mix title ("Jaxx Club Mix" by Basement Jaxx) doesn't count as a remixer.

## 3. Beatport for the review pile (optional, very effective)
Beatport lists every mix of a release with its exact length, but it blocks scripts. Use **Claude in Chrome** in the user's browser (load the Chrome browser skill first): open `https://www.beatport.com` in a tab, then run JavaScript in that tab for each batch of songs:
```js
const r = await fetch('/search/tracks?q=' + encodeURIComponent(q) + '&per_page=50');
const html = await r.text();
const data = JSON.parse(html.match(/<script id="__NEXT_DATA__"[^>]*>(.*?)<\/script>/s)[1]);
// dig for track objects: name/track_name, mix_name, length (ms or "m:ss"), artists[].name, remixers[].name
```
This covered 310 songs in about 15 minutes. Results where the **main artist differs** from the library's go to review, not straight to the list. Beatport is for **looking up** versions. Whether to buy there depends on `buying` in the config.

## 4. Download
Pass `extended-list.txt` (plus approved review items) to **get-songs**. It already knows the user's sources and version preference. Write lines as `Artist - Title (Mix Name)`, and clean them first:
- trim repeated mix names and very long artist lists
- **drop any line whose mix name equals the current version**, because those would just re-download the radio edit

## 5. Verify by length
```bash
uv run <skill>/scripts/verify_downloads.py "$WORK/matches.json" "<download folder>" [--since "YYYY-MM-DD HH:MM"]
```
Downloaders often save the radio edit under the extended name: **62 of 364** in a real run. The filename proves nothing; the length does.
- **OK** → move into the new library's genre folder.
- **TOO-SHORT** → reject, and put it back on the list for another source.
- **CHECK** → long enough, but not the expected length. Listen, or compare on Beatport.
- **MISSING** → still to get. Write `Still missing <date>.txt`.

Also check the download folder's **leftovers**: extended mixes the user grabbed separately end up there too. Downloaders can keep delivering after a list looks "done", so re-check for new files before closing out.

## 6. Pick the best version to mix (mixability)
Longer isn't always better: a version with a clean kick intro and outro beats one with a fade or a beatless intro.
```bash
uv run <skill>/scripts/mixability.py pick "<new library>" "<old library>" "<downloads>" --out "$WORK/mix_plan.csv"
```
List the new library **first**: what's already there is kept unless a challenger beats it by 0.15 or more. Per song, the scoring weighs beat strength in the first and last 16 s, length, real quality, and penalties for fades, "(Mixed)" cuts and leading silence. Different remixes never compete (the remixer is part of the song key). When a song has two genuinely different mixes worth keeping, keep both.

Show the user the plan: songs where the old version beats the download, and where a leftover file wins. After approval, move losers to a sibling folder such as `<new library>/../Not Kept <date>/`, never delete them, and log every move to a CSV in Reports.

## 7. Point the DJ software at the new files
rekordbox: use **rekordbox-tools → repoint**. It swaps playlist entries to the new files in place, keeps playlists, keeps cues where the audio is identical, and resets analysis where it changed. Other software: import the new folder as a fresh crate.

## Pitfalls that already happened
- **Prefix bug**: checking `path.startswith(".../DJ Library")` also matched `DJ Library 9.11`, and 18 files were skipped. Always compare with a trailing separator.
- The user may be changing the folder (or another session may be) while you work. Before moving files, re-scan and reconcile against your plan.
- macOS python.org builds can fail HTTPS certificate checks and silently retry forever. The scripts use certifi or curl. If lookups hang, that's the first thing to check.
