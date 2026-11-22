# Changelog

## 0.3.0 (2026-11-22)
- First full test pass on a real library: setup, get-songs via Offline DJ, audio-quality, organize-library scan + BPM/key, setlist-id, upgrade-to-extended matching, rekordbox repoint (on a DB copy).
- organize-library: `analyze_audio.py` and `enrich.py` read the same `PROTECTED` setting as `scan.py` (no more hardcoded folder names).
- README: Claude Desktop install steps; MIT license.

## 0.2.1
- setlist-id: cache and tracklists live outside the plugin folder (`SETLIST_ID_HOME`, `SETLIST_ID_OUT`), so plugin updates don't wipe them.

## 0.2.0
- Renamed get-songs → dj-toolkit. Added setlist-id, organize-library, audio-quality, upgrade-to-extended, rekordbox-tools, dj-troubleshooting.

## 0.1.0
- get-songs with Offline DJ (Telegram), Soulseek, streamrip, Beatport, Bandcamp and yt-dlp platform skills.
