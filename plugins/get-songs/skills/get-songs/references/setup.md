# Setup interview

Goal: learn this user in about 5 minutes, then write `~/.claude/get-songs/config.md` and `platforms.md` from the templates in `../templates/`.

Keep it conversational. Use AskUserQuestion with multiple-choice options where you can, so the user isn't typing essays. Group questions. **Look before asking**: check the machine for clues first, and confirm what you found instead of asking from scratch.

## 0. Look around first (silently)

- OS and architecture (`uname -sm`, or Windows).
- Installed music apps: `/Applications` (macOS) or Program Files. Look for OfflineDJ, rekordbox, Serato, Traktor, VirtualDJ, djay, Telegram, Tidal, Qobuz, Deezer, Spotify, SoundCloud and Beatport apps.
- Likely music folders: `~/Music/*`, `~/Downloads`, any folder holding lots of .flac/.mp3/.aiff/.wav files (use `find` with `-maxdepth 3`, counting by folder).
- Tools already present: `sldl`/`sockseek`, `streamrip` (`rip`), `yt-dlp`, `ffmpeg`/`ffprobe`, `python3`.
- Whether browser automation (Claude in Chrome) is available. Cart platforms need it.

## 1. Who are you? (one question)
"What do you mainly need songs for?" → DJing (club sets) / DJing (events, weddings) / Personal listening / Producing or remixing. This sets the defaults in step 2. DJs default to extended versions, lossless and dedupe on.

## 2. Preferences (one AskUserQuestion with up to 4 questions)
- **Version**: Extended / club versions (recommended for DJs) · Exactly the version I write · Original / radio versions.
- **Quality**: Lossless if possible, 320 MP3 minimum (recommended) · Lossless only · Any decent quality (256+).
- **Lossy last resort**: when nothing else finds a track, allow YouTube/SoundCloud quality? Yes, but flag it · No, skip the track.
- **Buying**: when a track can only be bought, should I add it to your cart (you pay yourself) on Beatport / Bandcamp / other? Yes · No, never buy.

## 3. Sources: what do you already use? (multiSelect)
Offer what step 0 found first, then the common ones:
- **Paid download tools**: Offline DJ, or other (type the name)
- **Streaming subscriptions with lossless**: Qobuz, Tidal, Deezer
- **Stores**: Beatport, Bandcamp, Traxsource, Juno Download, iTunes
- **DJ pools / record pools**: BPM Supreme, DJcity, ZipDJ, Music Worx...
- Nothing paid, free sources only

**Soulseek** (free, P2P, lossless-friendly) is offered to everyone. Recommend it as a fallback and explain in one line what it is.

For every selected platform:
- If a built-in skill exists (see table below), run its **setup section** now.
- If not, run `learn-platform.md` for it. You can do this after the rest of setup, so the user isn't stuck waiting.

| Platform | Skill |
|---|---|
| Offline DJ | `platform-offlinedj` (Telegram bridge) |
| Soulseek | `platform-soulseek` (sldl / Sockseek) |
| Qobuz / Tidal / Deezer / SoundCloud Go+ | `platform-streamrip` |
| Beatport (store) | `platform-beatport` (add to cart) |
| Bandcamp | `platform-bandcamp` (add to cart / collection) |
| YouTube / SoundCloud (free) | `platform-ytdlp` |

## 4. Folders
- **Download folder**: where new tracks land. Suggest `~/Music/get-songs` (or what they already use, e.g. Offline DJ's folder).
- **Library folders to check for duplicates**: suggest what step 0 found. Read-only, never modified.
- **After download**: nothing / sort into genre folders / add to rekordbox-Serato playlist / rename to "Artist - Title (Version)".
- **Naming**: keep the source's names, or "Artist - Title (Version)".

## 5. Source order
Propose an order and let them reorder. Sensible default: free-to-use tools they already pay for first, then Soulseek, then carts, then lossy last.
`offlinedj → streamrip → soulseek → cart:beatport → cart:bandcamp → ytdlp`

## 6. Write the files
1. `mkdir -p ~/.claude/get-songs/{secrets,runs} && chmod 700 ~/.claude/get-songs/secrets`
2. Fill in `../templates/config.md` → `~/.claude/get-songs/config.md`
3. Fill in `../templates/platforms.md` → `~/.claude/get-songs/platforms.md`, one row per platform with status `ready` / `needs-login` / `to-learn` / `not-used`.
4. Show a 6-line summary and offer a test run: "Want to try it with 2-3 songs now?" A real test is the best way to catch setup problems.

Re-running setup later should prefill everything from the existing config and only ask about changes.
