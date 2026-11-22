---
name: dj-troubleshooting
description: Quick, proven fixes for common DJ setup problems - no sound from a controller (DDJ-FLX4 and similar Pioneer/AlphaTheta controllers), quiet headphones, rekordbox analysis stuck or extremely slow, tracks that won't analyse, drifting beatgrids and odd BPMs, missing tracks after moving files. Diagnoses on the user's machine where possible. Use when the user types /dj-troubleshooting or describes any DJ software or controller problem ("no sound", "headphones too quiet", "analysis stuck", "rekordbox frozen on analyzing", "grid is off").
---

# DJ troubleshooting

Diagnose first with what you can check on the machine (processes, settings files, the database via rekordbox-tools). Then give the user **only the steps that apply**, in order, and say which menu names come from memory, since they move between versions. Read `dj_software` and `controller` from `~/.claude/dj-toolkit/config.md` if it exists.

When the user asks a question ("why is…", "how do I…"), answer it and don't change anything. Act only when they ask you to.

## No sound from the controller (rekordbox + DDJ-FLX4 / DDJ-400 class)
Work through these in order; the first ones fix most cases:
1. **Mode**: rekordbox must be in **PERFORMANCE** mode, not EXPORT (top-left switch).
2. **Audio device**: Preferences → Audio → Audio: select the controller (e.g. **DDJ-FLX4**), mixer mode **Internal Mixer**. Outputs: Master → 1&2, Headphones → 3&4.
3. **Levels on the hardware**: MASTER LEVEL up, channel faders up, crossfader centred or on the playing side, **TRIM up**. *In a real case the cause was TRIM turned all the way down.* Watch the channel level meters: if they move, the audio is reaching the controller.
4. Speakers or amp connected to MASTER OUT (RCA), powered and turned up. Test headphones on the controller to split "controller problem" from "speaker problem".
5. Cable and power: use the USB-C cable that came with it, plugged straight into the computer (not a hub). On macOS, check System Settings → Privacy & Security if the driver was blocked.

## Headphones too quiet
1. **HEADPHONES LEVEL** knob up, and **MIXING** knob towards CUE (not MASTER) to hear the cued channel.
2. **CUE** button lit on the channel you want to hear.
3. **TRIM** on that channel set so the meter reaches about orange at peaks. A low trim makes everything quiet.
4. USB power: some laptops underpower bus-powered controllers. Try another port or a powered connection.
5. High-impedance headphones (250 Ω and up) are quiet on bus-powered controllers. Use 32-80 Ω DJ headphones.

## rekordbox analysis stuck / very slow ("Analyzing 608" not moving)
Diagnose:
- Is it writing anything? Check `~/Library/Pioneer/rekordbox/share/PIONEER/USBANLZ` (Windows: `%APPDATA%\Pioneer\rekordbox\share\PIONEER\USBANLZ`). No new `.DAT` files for minutes means it's stuck.
- High CPU while the same files stay open (`lsof -p $(pgrep -x rekordbox)` on macOS) means it's stuck on a few tracks.
- Thread samples (macOS: `sample rekordbox 5`) showing `AnalyzeJobCloudSearch` / `NetAnalysis::searchTracks` mean it's waiting on **Cloud Analysis**.

Fix (proven): **Preferences → Analysis → Track Analysis → untick Cloud Analysis**, force-quit rekordbox, reopen and re-analyse. The setting is stored as `trackAnalysisSettingsNetworkAnalysis val="1"` in `~/Library/Application Support/Pioneer/rekordbox6/rekordbox3.settings`. Read it to confirm, but change it in the app, not the file.

Also check:
- **32-bit float WAVs** can fail to analyse. Convert them to 24-bit (`ffmpeg -i in.wav -c:a pcm_s24le out.wav`, into a new file, keeping the original).
- Very large batches: analyse in chunks of about 100.

## Grid drifts / BPM looks wrong
Use **rekordbox-tools → bpm triage**. In short: a BPM like 127.99 means the true tempo is 128. Set Track Analysis Mode to Normal and a sensible BPM range, re-analyse, or fix the grid by hand (Grid Edit → 1st beat → type the BPM → lock). Real decimals on older records are correct.

## Tracks missing ("!" icon) after moving files
rekordbox: **File → Library → Display All Missing Files → Auto Relocate** and choose the folder they moved to. For many files or renamed files, use **rekordbox-tools** (`missing`, then `map`/`plan`/`apply`).

## When it's something else
Collect the basics: software and version, controller, OS, what changed recently, and exactly what the user sees. Check the software's logs and settings files read-only. Search the manufacturer's support pages and forums for the exact symptom. Once something works, offer to add the fix to this skill for next time.
