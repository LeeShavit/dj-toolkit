# get-songs 🎧

A Claude Code plugin: give Claude any list of songs, and it downloads them in the best quality and **in the version you actually want** (extended / club mixes for DJs). It uses the tools you already have, checks every file, and gets smarter about your setup over time.

```
/get-songs
John Summit - WITH ME
Darude - Sandstorm
https://open.spotify.com/playlist/...
```
→ `Got 31/35 ✅ (FLAC 22 · MP3 320 9) · ⚠️ 1 to check · 🛒 2 in your Beatport cart · ❌ 2 not found`

## Install

In Claude Code:
```
/plugin marketplace add LeeShavit/get-songs
/plugin install get-songs@get-songs
```
Then run `/get-songs setup`. Claude interviews you for about 5 minutes (what you use, your preferences, your folders) and sets everything up.

## What it does

- **Learns you once**: version preference (extended / exact / original), minimum quality, folders, whether to add buy-only tracks to your cart. Saved in `~/.claude/get-songs/config.md`, which you can edit by hand.
- **Uses your sources in your order**, sending each track to the next source only if the previous one missed it:

  | Source | How | Cost |
  |---|---|---|
  | Offline DJ | Claude messages the Offline DJ Telegram bot from your account | your subscription |
  | Qobuz / Tidal / Deezer | streamrip CLI with your account | your subscription |
  | Soulseek | sldl / Sockseek CLI, available to everyone | free |
  | Beatport / Bandcamp | adds to **your cart** in Chrome; you pay yourself | per track |
  | YouTube / SoundCloud | yt-dlp, last resort, labelled LOSSY | free |

- **Checks every file**: right version (not a radio edit or a different remix), plausible length, real lossless. Wrong files go to `_rejected/` and that track tries the next source.
- **Skips what you already have** by scanning your library folders (read-only).
- **Learns new platforms**: tell it "I use DJcity" (or anything else). Claude researches how to drive it, tests with a track, and writes a new skill to `~/.claude/skills/get-songs-platform-<name>/`, so it works next time. You can share these skills with friends.

## Commands
- `/get-songs <songs | file | playlist link>`: download
- `/get-songs setup`: first-time setup or re-setup
- `/get-songs add <platform>`: teach it a new source
- `/get-songs settings`: change preferences
- `/get-songs status`: platforms and last run

## Your data
Everything personal stays on your computer in `~/.claude/get-songs/`: config, platform notes, run reports, and `secrets/` (API keys and sessions, readable only by you). Nothing is sent anywhere except to the services you set up.

## Requirements
Claude Code · Python 3.10+ · `ffmpeg` recommended · Claude in Chrome for the Beatport and Bandcamp carts.

## Fair use
You're responsible for following copyright law and each service's terms where you live. get-songs never completes purchases and never bypasses DRM or paywalls. Support the artists you play. 🙏
