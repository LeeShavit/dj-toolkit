---
name: platform-ytdlp
description: Last-resort download of a track from YouTube or SoundCloud with yt-dlp - lossy quality (about 128-256 kbps), always labelled as such. Good for SoundCloud-only bootlegs, edits and free downloads. Use only when get-songs has allow_lossy enabled and better sources failed, or the user explicitly asks to grab something from YouTube or SoundCloud.
---

# YouTube / SoundCloud (yt-dlp) - lossy

yt-dlp downloads audio from YouTube, SoundCloud and many other sites. The quality is **lossy** (YouTube ~128-160 kbps Opus/AAC; SoundCloud 128 kbps MP3/Opus, or the original if the artist enabled downloads), so it's not club-grade. Converting to MP3 320 doesn't add quality, so don't pretend it does.

## Setup
`brew install yt-dlp ffmpeg` (macOS) · `pipx install yt-dlp` · `winget install yt-dlp`. Keep it updated (`yt-dlp -U`, or via the package manager), since sites change often.

## Download
```bash
# best match from a search, keep original codec (no fake upscaling), add tags + cover
yt-dlp "ytsearch1:Artist - Title Extended Mix" -x --audio-format best --embed-metadata --embed-thumbnail \
  -o "<download_folder>/_lossy/%(title)s.%(ext)s"
yt-dlp "scsearch1:Artist Title" -x ...          # SoundCloud search
yt-dlp "<url>" -x ...                           # direct link (most reliable)
```
- **SoundCloud free downloads**: if the track has a "Free Download" button (often a link to hypeddit/toneden or a direct original file), that's often the artist's own WAV/MP3 320. Prefer it, and tell the user.
- Check the match before keeping it: the uploader is the artist or label, and the duration matches the target version. Search results love lyric videos, slowed/sped-up versions and nightcore edits.

## Reporting
Put files in `_lossy/` and mark them **LOSSY** in the report, so the user knows to replace them later.
