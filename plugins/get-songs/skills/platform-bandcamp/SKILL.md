---
name: platform-bandcamp
description: Find tracks on Bandcamp, add paid ones to the user's Bandcamp cart (the user pays - never check out), grab free / name-your-price downloads with the user's OK, and download already-purchased items from their collection. Use when get-songs routes tracks to Bandcamp, or the user mentions Bandcamp for getting tracks.
---

# Bandcamp (cart, free downloads, collection)

Bandcamp is where many underground, indie and edit producers sell directly, and some give tracks away free or "name your price". Uses **Claude in Chrome** with the user's login. Load the Chrome browser skill first.

**Never complete a payment.** Adding to the cart is the end of the line for paid items.

## Setup (one time)
1. The user logs in to bandcamp.com in the Chrome that Claude in Chrome controls.
2. Ask their preferred download format (FLAC, recommended; AIFF; WAV; MP3 320).
3. Ask: for "name your price" tracks, is €0 / free OK to grab automatically, or always add to the cart? Record the answer in `config.md`.

## Find and add
1. Search `https://bandcamp.com/search?q=<artist title>&item_type=t` (tracks), or search albums if the track is part of an EP.
2. Match the artist, title and version. Bandcamp often lists the extended version as the main track.
3. Paid: "Buy Digital Track" → enter the price (the minimum, unless the user says otherwise) → **Add to cart**. Stop.
4. Free / name-your-price with the user's OK: enter 0 → download → pick the format → save to `download_folder`. Some ask for an email; ask the user before entering one.

## Purchased collection
`https://bandcamp.com/<username>` → collection → each item's download link → choose the format. The zip/flac lands in the browser's Downloads folder: move it to `download_folder`, unzip if needed, and verify.
