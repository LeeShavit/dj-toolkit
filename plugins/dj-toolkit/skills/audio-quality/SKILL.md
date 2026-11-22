---
name: audio-quality
description: Find fake lossless and upscaled audio - FLAC/WAV/AIFF files that were really made from MP3s, and "320" MP3s upscaled from 128 kbps - by measuring where each file's frequencies really stop (like Fakin' The Funk / audiocheck). Writes a report, can tag verdicts into the Comment field for sorting in rekordbox/Serato/Traktor, and hands fakes to get-songs for a real copy. Use when the user types /audio-quality or /audiocheck, asks whether files are really lossless, wants to check download quality, finds a track sounding dull/muffled on a big system, or before organizing or uploading a batch.
---

# Audio quality check (fake lossless detector)

An MP3 encoder removes the highest frequencies: everything above about 16 kHz at 128 kbps, and above about 19.5-20 kHz at 320 kbps. Converting that MP3 to FLAC or WAV, or re-encoding it as "320", **doesn't bring them back**. On a club system, the missing top end and MP3 artifacts are audible.

The script looks for the encoder's signature: a **cliff**, a flat spectrum that suddenly falls 15-30 dB within 1 kHz at or below 20.5 kHz. Real masters roll off gradually, or have a filter edge at 21 kHz or higher, which is normal and ignored. A plain "where does the sound stop" cutoff isn't enough. Real lossless files and 320 sources both reach about 20-21 kHz, and a cutoff test passed two known fakes in calibration, while the cliff test caught both.

## Run
```bash
uv run <skill>/scripts/audiocheck.py "<folder or files>" [--tag] --protect <protected folders...>
```
- Pass every `protected_folders` entry from `~/.claude/dj-toolkit/config.md` with `--protect`. The check itself is read-only, but `--tag` writes to files, and protected folders must never be written.
- **Ask before `--tag`.** It changes files (it appends `AUDIOCHECK: FAKE (16.1 kHz)` to the Comment tag and keeps existing comment text). Useful because the user can then sort by Comments in their DJ software.
- Runs in parallel, roughly 1-2 s per file. Run big folders in the background.
- Writes `audiocheck-report-<date>.txt` and `.csv` to `~/.claude/dj-toolkit/runs/` (`--out` to change).

## Verdicts
| Verdict | Meaning | What to do |
|---|---|---|
| **FAKE** | A lossless file with a lossy encoder's "cliff" (flat, then a 15+ dB fall within 1 kHz somewhere at or below 20.5 kHz). The cliff's position estimates the source: about 16 kHz means 128 kbps, about 20 kHz means 320 kbps. Also a "320" MP3 upscaled from 128 | Replace it |
| **SUSPECT** | A "320" MP3 with a cliff at 17.5-19 kHz, probably upscaled from 160-192 kbps | Replace it if a real copy exists |
| **CHECK** | A softer 12-15 dB drop, or content that stops below 19 kHz but rolls off gradually (dark masters, vinyl rips, older tracks) | Listen, or look at a spectrogram |
| **LOW** | An honest lossy file under 256 kbps | Upgrade it if it's a track they play out |
| **OK** | Content where it should be | Nothing |

Also flagged: "hi-res" 96 kHz files whose content stops at about 22 kHz, which are upsampled from CD quality. They're not bad, just not hi-res.

## After the report
- Summarise the counts and list the FAKE and SUSPECT files.
- Offer to **re-download real copies** with **get-songs**. Pass the exact artist, title and version, and note that the current copy is fake, so it isn't skipped as "already had". Tell get-songs which sources produced fakes before (e.g. a particular Soulseek user or a site), so it avoids them.
- Never delete fakes. When a real copy arrives, the user decides (move to Trash, or keep both while testing).
- Limits: a very quiet or very dark track (deep dub, ambient intros) can read low. The script measures 3 windows across the track and ignores near-silent frames, but if a CHECK or SUSPECT verdict surprises you, say so and suggest listening.

## Related
- `get-songs` runs a lighter version of this check on every download.
- `organize-library` keeps `AUDIOCHECK` comment text when it cleans tags.
- `upgrade-to-extended` uses the same cutoff idea when it picks the best version of a song.
