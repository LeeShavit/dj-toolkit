# DJ toolkit config
<!-- Written by /dj-setup. Safe to edit by hand. No passwords or keys here: those live in ~/.claude/dj-toolkit/secrets/ -->

## About me
- use: dj-club                    # dj-club | dj-events | listening | producing
- dj_software: rekordbox 7        # rekordbox <ver> | serato | traktor | virtualdj | djay | none
- controller: DDJ-FLX4            # optional, helps troubleshooting
- os: macOS

## Library
- music_root: ~/Music
- library_folders:                # where the DJ music lives (read for duplicates, scans, upgrades)
  - ~/Music/My Library
- protected_folders:              # NEVER modified by any tool: no tags, moves, renames or deletes
  - ~/Music/Music                 # Apple Music library
  - ~/Music/rekordbox             # app files
- new_batches_go_to: ~/Music/DJ New {YYYY-MM}   # where organize-library puts new music
- genres:                         # genre folders = genre tags. "&" is written "and" on disk
  - Tech House
  - Melodic & Deep House
  - Dance Pop & Remixes
  - Classic House
- one_copy_per_song: true         # different mixes/remixes count as different songs and are kept
- delete_mode: trash              # always Trash, never permanent delete

## Downloads (get-songs)
- version_preference: extended    # extended | exact | original
- min_quality: 320                # lossless | 320 | 256
- prefer_lossless: true
- allow_lossy: false              # last-resort YouTube/SoundCloud quality, clearly flagged
- buying: cart-only               # cart-only (add to cart, user pays) | never
- naming: source                  # source | "Artist - Title (Version)"
- download_folder: ~/Music/get-songs
- after_download: none            # none | organize-library | rename
- source_order: soulseek, ytdlp

## Setlists (setlist-id)
- setlists_folder: ~/Music/Setlists
- shazam_country: US

## Approvals already given
<!-- e.g. "telegram-send: yes (2026-11-22)", "beatport-cart: yes", "rekordbox-db-write: ask every time" -->
