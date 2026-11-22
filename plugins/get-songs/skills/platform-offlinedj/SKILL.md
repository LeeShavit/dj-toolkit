---
name: platform-offlinedj
description: Download songs with Offline DJ (paid desktop app, FLAC/320) by sending track names to its Telegram bot from the user's own Telegram account - no clicking in the app. Includes one-time Telegram setup (API keys + QR login). Use when get-songs routes tracks to Offline DJ, or the user wants Claude to control Offline DJ, send songs to the Offline DJ bot, or connect Offline DJ to Telegram.
---

# Offline DJ (via Telegram)

Offline DJ is a paid desktop app (Windows/macOS) that downloads tracks in FLAC or 320 MP3 from song names. It has no CLI. But its **Telegram bot** queues songs for the app, even while the app is closed. Bots can't message other bots, so Claude sends from the **user's own Telegram account** using Telegram's official user API (Telethon). The app then downloads automatically.

All scripts are in this skill's `scripts/` folder. Data lives in `~/.claude/get-songs/secrets/telegram/` (keys and session, chmod 600). Python packages go in the venv at `~/.claude/get-songs/venv`.

## Setup (one time)

1. **The user connects Offline DJ to Telegram** inside the Offline DJ app (Integrations → Telegram) and tells you the bot's @username.
2. **Python env**: `python3 -m venv ~/.claude/get-songs/venv && ~/.claude/get-songs/venv/bin/pip install -q telethon "qrcode[pil]"`. Use `VPY=~/.claude/get-songs/venv/bin/python` below.
3. **API keys**: the user creates an app at https://my.telegram.org → API development tools (any name) and gets `api_id` and `api_hash`. There are two ways to save them:
   - Private (recommended): the user runs `$VPY <skill>/scripts/tg_keys.py` in their own Terminal. It prompts, hides the hash, and saves it.
   - Or the user pastes them to you, and you run `$VPY <skill>/scripts/tg_keys.py --api-id N --api-hash H --bot BOTNAME`.
4. **Login by QR code** (codes by SMS or in-app often never arrive for API logins, so don't bother with them): run `$VPY <skill>/scripts/tg_qr_login.py` **in the background**. It opens a QR image on screen and refreshes it every ~25 s. Tell the user: phone → Telegram → Settings → Devices → **Link Desktop Device** → scan. If it prints `2FA_REQUIRED`, ask the user for their cloud password, or let them type it: `TG_2FA='...' $VPY ...tg_qr_login.py`. Success prints `Logged in OK` and the bot name.
5. Explain once: the session file gives full account access, like any logged-in device. It's stored only on this computer, and they can revoke it in Telegram → Settings → Devices.
6. Record in `platforms.md`: status `ready`, the bot's @username. Record in `config.md` approvals: `telegram-send: yes`.

## Download tracks

```bash
TG="$VPY <skill>/scripts/tg.py"
$TG send "Artist - Title (Extended Mix)"       # one track; prints the bot's reply
$TG send-file /path/list.txt                    # one message per line; prints how many the bot confirmed
$TG read 20                                     # recent chat with the bot
```

Plain text `Artist - Title (Version)` works best, one track per message. The bot also accepts Spotify / YouTube / Beatport / SoundCloud / Apple Music links and Shazam shares.

**Send the exact version you want.** Offline DJ looks up what you write, so `(Extended Mix)` in the text is what gets you the extended version.

## Reading results

- Bot reply `✅ SENT! I've sent <track> to 1 computer!` only means the track is **queued**, not downloaded. `0 computers` means the app isn't linked.
- Files land in Offline DJ's download folder: the `folder` key in its settings file, usually `<folder>/Unsorted Music/`. Settings: macOS `~/Library/Application Support/OfflineDJ/offlinedj_settings.json`, Windows `%APPDATA%\OfflineDJ\`. Read that file to find the folder. Its queue files are encrypted; ignore them.
- Not-found tracks are written to `NOT_FOUND.txt` in the same folder. The app also shows not-found and **"you already have this song"** pop-ups **only inside its window**, so you can't see those. That's why get-songs checks for duplicates *before* sending. If a track neither arrives nor appears in NOT_FOUND within ~5 minutes, ask the user what the app window shows.
- Downloads usually arrive within 10-60 s per track while the app is open. Watch for new files in a background loop rather than blocking:
  `find "<folder>" -newermt "<send time>" -type f \( -name '*.flac' -o -name '*.mp3' \)`
- Relevant settings in its JSON: `download_quality_order`, `similar_song_behavior` (`always_accept` can grab a near-match, so verify the version), `download_from_youtube` (if enabled, some files may be lossy).

## Gotchas
- The app itself can be closed; the bot keeps a queue. But nothing downloads until the app runs.
- Sending a lot at once is fine (1.5 s between messages is built in).
- If `tg.py` says "Not logged in", rerun the QR login.
