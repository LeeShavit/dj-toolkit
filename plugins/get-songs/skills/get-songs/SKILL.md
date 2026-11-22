---
name: get-songs
description: Download any list of songs to the user's computer in the best quality and in the version they prefer (extended / club / exact), using every source they have - paid tools like Offline DJ (via Telegram), streaming subscriptions, Soulseek, Beatport/Bandcamp carts, and more. Runs a one-time setup interview the first time. Use this whenever the user types /get-songs, pastes a list of songs or a playlist link and wants the tracks, says "download these songs", "get me this track", "find the extended version of...", shares a Shazam/Spotify/YouTube list to download, or wants to add a new download platform - even if they don't say "get-songs".
---

# get-songs

Turns "here are some songs" into verified audio files on disk. It works for anyone: it learns the user's tools and taste once, saves them, and uses them every time.

All per-user state lives in **`~/.claude/get-songs/`** (the "home"). The plugin itself is replaced when it updates, so nothing user-specific is ever written inside the plugin folder.

```
~/.claude/get-songs/
├── config.md          # who the user is: preferences, folders, accounts, source order
├── platforms.md       # every platform: status, which skill drives it, notes from past runs
├── secrets/           # API keys, sessions (chmod 700). Never in the .md files.
├── venv/              # Python env for helper scripts (created on demand)
└── runs/              # one report per download run
```

Platform know-how lives in skills, one per platform:
- Built in (this plugin): `platform-offlinedj`, `platform-soulseek`, `platform-streamrip`, `platform-beatport`, `platform-bandcamp`, `platform-ytdlp`.
- Learned: `~/.claude/skills/get-songs-platform-<slug>/SKILL.md`. These are written by this skill when it learns a new platform, and load automatically in future sessions.

## Decide what was asked

| The user said | Do |
|---|---|
| `/get-songs setup`, or `config.md` doesn't exist | **Setup**: read `references/setup.md` and follow it. If they also gave songs, download those right after setup. |
| `/get-songs <songs / file / link>` or any request for tracks | **Download run** (below) |
| `/get-songs add <platform>`, or they mention a source that isn't in `platforms.md` | **Learn a platform**: read `references/learn-platform.md` |
| `/get-songs settings` / "change my preferences" | Show `config.md` as a short summary, edit what they ask, and save it |
| `/get-songs status` | Summarise `platforms.md` and the last run report |

Always read `config.md` and `platforms.md` first. They're short, and every decision depends on them.

## Download run

### 1. Parse the input into a track list
Accept anything: pasted lines, a .txt/.csv file, a Spotify / YouTube / SoundCloud / Apple Music / Beatport playlist link, a Shazam export, a screenshot of a tracklist. Normalise each track to `Artist - Title (Version)`. For links, extract the tracklist first (use a platform's own tool if one can read playlists, otherwise fetch the page). Show the parsed list back only if something was ambiguous; otherwise just continue.

### 2. Choose the target version for each track
Apply `version_preference` from config:
- **extended** (DJs): look for Extended Mix / Extended Version / Club Mix / extended remix. If the user named a version, keep it. If they didn't, search the web (Beatport, Traxsource, Discogs and DJ-pool listings are good evidence) and pick the official extended. If none exists, a well-known extended remix is next best, then the original. Say which one you chose and why in the report.
- **exact**: get exactly the version named; if none is named, the original release.
- **radio/original**: the standard release.

Read `references/versions.md` for version-matching rules and the traps that cause wrong downloads.

### 3. Skip what they already have
Run `scripts/find_existing.py` with the list and the `library_folders` + `download_folder` from config. Tracks that already exist in the target version are skipped and listed as "already had". If a different version exists (e.g. the radio edit when you want the extended), still download the target version, and mention the existing copy.

### 4. Route through sources in the user's order
`source_order` in config lists the platforms by priority, e.g. `offlinedj → streamrip → soulseek → cart:beatport → ytdlp`. For each source in turn:
1. Load that platform's skill (built in, or learned in `~/.claude/skills/`).
2. Send it the tracks that are **still missing**, and only those.
3. Collect results: downloaded / not found / wrong version / needs user.

Batch where the platform allows it, since most can take a whole list at once. Run slow sources (Soulseek) in the background and keep working.

**Cart platforms** (Beatport, Bandcamp, ...) only *add to cart* and never check out. Paying is always the user's own click. Only use them when `buying` in config allows it, and give them the tracks no free or subscription source found.

**Lossy sources** (yt-dlp: YouTube / SoundCloud) are a last resort, used only when `allow_lossy: true`. Label the result clearly, because a 128-256 kbps file isn't club quality.

### 5. Verify every file
Run `scripts/check_audio.py <files>`. For each track, confirm:
- **Format/quality** meets `min_quality` (and flag FLACs under ~500 kbps as possibly fake lossless).
- **Version**: the filename and tags match the target version, not a different remix or edit.
- **Length** makes sense: an extended version is usually 1-3 minutes longer than the radio edit. A 2:45 "Extended Mix" is suspicious.

Bad files don't count as found. Move them to `<download_folder>/_rejected/` (never delete), and pass the track on to the next source.

### 6. Report
Write `~/.claude/get-songs/runs/<YYYY-MM-DD_HHMM>.md` and show the user a compact summary:

```
Got 31/35 ✅   (FLAC 22 · MP3 320 9)   → ~/Music/Downloads/get-songs
• via Offline DJ 27 · Soulseek 4
⚠️ Check: Axel F (Extended) is only 2:44
🛒 In your Beatport cart (2): ...
❌ Not found anywhere (2): ...
```

Then update `platforms.md` with anything learned, such as hit rate or a quirk ("Offline DJ shows duplicate pop-ups only in its window"). That's how the skill gets better for this user over time.

### 7. Post-processing (only if configured)
If `after_download` in config says so, hand off: e.g. move files into genre folders, tag them, or tell the user how to import into rekordbox / Serato. Don't touch library folders unless config allows it. Libraries are often carefully curated.

## Principles

- **The user's accounts, the user's money.** Use only accounts and subscriptions the user owns and set up. Never check out or confirm a payment. Never share credentials with any service other than the one they belong to.
- **Secrets stay out of markdown.** Store keys and sessions in `~/.claude/get-songs/secrets/` (chmod 600). `config.md` only says *that* an account is set up.
- **Ask before outward actions the user hasn't approved before**: sending from their Telegram account for the first time, adding to a cart for the first time, creating an account. After they say yes once, `config.md` records the approval and you don't ask again.
- **Don't overwrite or delete user files.** New downloads go to `download_folder`. Rejected files go to `_rejected/`. Remove duplicates only when asked, and move them to the Trash rather than deleting.
- **Report honestly.** "Bot confirmed" doesn't mean "downloaded". Count only files you verified on disk.
- Users are responsible for respecting copyright and each platform's terms in their country. Don't help get around DRM on purchased or streamed files beyond what the user's own tool does by itself.
