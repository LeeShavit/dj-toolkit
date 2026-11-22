# get-songs config
<!-- Written by /get-songs setup. Safe to edit by hand. No passwords or keys here: those live in ~/.claude/get-songs/secrets/ -->

## About me
- use: dj-club            # dj-club | dj-events | listening | producing
- dj_software: rekordbox  # rekordbox | serato | traktor | virtualdj | djay | none

## Preferences
- version_preference: extended   # extended | exact | original
- min_quality: 320               # lossless | 320 | 256
- prefer_lossless: true
- allow_lossy: false             # last-resort YouTube/SoundCloud quality, clearly flagged
- buying: cart-only              # cart-only (add to cart, user pays) | never
- naming: source                 # source | "Artist - Title (Version)"

## Folders
- download_folder: ~/Music/get-songs
- library_folders:               # read-only, used for duplicate checks
  - ~/Music/My Library
- after_download: none           # none | genre-folders | rename | rekordbox-playlist

## Sources (tried in this order)
- source_order: offlinedj, soulseek, cart:beatport, ytdlp

## Approvals already given
<!-- e.g. "telegram-send: yes (2026-11-22)", "beatport-cart: yes" -->
