---
name: platform-beatport
description: Find the exact DJ version of a track on Beatport and add it to the user's Beatport cart (the user pays themselves - never check out), then pick up purchased files from their library. Also the best place to look up which versions exist (Extended / Original Mix / remixes) and their lengths. Use when get-songs routes tracks to Beatport, or the user wants tracks added to their Beatport cart.
---

# Beatport (add to cart only)

Beatport sells DJ-ready files (WAV/AIFF/FLAC/MP3) and is the reference for which versions exist. This skill uses **Claude in Chrome** on the user's logged-in browser. Load the Chrome browser skill before the first browser step.

**Never click Checkout, Pay, or confirm a purchase.** Adding to the cart is where this skill stops. The user reviews and pays.

## Setup (one time)
1. Make sure Claude in Chrome is available, and ask the user to log in to beatport.com in that Chrome.
2. Ask their preferred format (Beatport lets you choose per cart item, or account-wide in settings: WAV, AIFF, FLAC or MP3).
3. Record in `platforms.md`: `ready`, cart-only. Record approval `beatport-cart: yes` in `config.md`.

## Add tracks to the cart
For each missing track:
1. Search `https://www.beatport.com/search/tracks?q=<artist title>`.
2. Pick the row whose **title, mix name and artists** match the target version (Beatport shows mix names like "Extended Mix" / "Original Mix" separately, plus the length). If several exist, prefer the target version from `versions.md`, then the official label release over re-uploads.
3. Click the cart / price button on that row. Confirm the cart count went up.
4. Note the price and track URL for the report.

When done, open the cart page and report: N tracks, total price, the cart link. Stop there.

## Using it for version lookup (free)
Even when the user won't buy, Beatport search results show which versions exist and their exact lengths. get-songs uses this to choose the target version and to check that downloaded files have the right length.

## After the user buys
Purchased files are under My Library → Downloads. If asked, download them there through the browser, then verify them with `check_audio.py`.
