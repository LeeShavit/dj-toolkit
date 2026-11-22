#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = [
#   "numpy",
#   "mutagen",
#   "imageio-ffmpeg>=0.5",
# ]
# ///
"""audiocheck - find fake lossless and upscaled audio files.

A file made from an MP3 keeps the MP3's high-frequency cutoff (about 16 kHz for 128 kbps,
19-20 kHz for 320 kbps) even after it is converted to FLAC/WAV or re-encoded at 320.
This measures where the spectrum really stops (max over 3 windows of the track) and
compares it with what the file claims to be.

usage:
  uv run audiocheck.py FOLDER_OR_FILES... [--tag] [--out REPORT_DIR] [--protect DIR ...] [--jobs N]

  --tag        append "AUDIOCHECK: <verdict> ..." to each file's Comment tag (keeps existing text)
  --protect    never write tags inside these folders (use for protected library folders)
  --out        where to write audiocheck-report-<date>.txt/.csv (default ~/.claude/dj-toolkit/runs)

Verdicts:  OK · CHECK (borderline - listen / view a spectrogram)
           SUSPECT ("320" MP3 probably upscaled from 160-192 kbps)
           FAKE (lossless file with a lossy encoder's cliff, or "320" upscaled from 128 kbps)
           LOW (honest lossy file below 256 kbps) · ERROR
"""
import argparse, csv, os, shutil, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import mutagen

AUDIO = (".flac", ".wav", ".aif", ".aiff", ".mp3", ".m4a", ".alac", ".ogg", ".opus")
LOSSLESS_EXT = (".flac", ".wav", ".aif", ".aiff")


def ffmpeg_bin():
    return shutil.which("ffmpeg") or __import__("imageio_ffmpeg").get_ffmpeg_exe()


FF = ffmpeg_bin()


def window_spectrum(path, start, sr):
    """Average power spectrum (dB, relative to the 1-4 kHz level) of an 8 s window, ignoring silent frames."""
    r = subprocess.run([FF, "-v", "quiet", "-ss", f"{start:.1f}", "-t", "8", "-i", path, "-ac", "1",
                        "-ar", str(sr), "-f", "s16le", "-"], capture_output=True)
    x = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32)
    n = 4096 if sr <= 48000 else 8192
    if len(x) < n * 4:
        return None
    frames = x[: len(x) // n * n].reshape(-1, n) * np.hanning(n)
    frames = frames[frames.std(1) > 300]      # skip near-silent frames (breakdowns, fades)
    if len(frames) < 4:
        return None
    db = 10 * np.log10((np.abs(np.fft.rfft(frames, axis=1)) ** 2).mean(0) + 1e-9)
    f = np.fft.rfftfreq(n, 1 / sr)
    return f, db - np.median(db[(f > 1000) & (f < 4000)])


def analyse_spectrum(f, rel):
    """cutoff = highest frequency within 50 dB of the reference.
    cliff  = the steepest drop (dB) across 1 kHz anywhere between 15 and 20.5 kHz, and where it is.
    Lossy encoders leave a cliff (flat, then a sudden 15-30 dB fall); real masters roll off gradually,
    or have a filter edge at 21 kHz or above, which is normal and ignored here."""
    above = np.where(rel > -50)[0]
    cutoff = int(f[above[-1]]) if len(above) else 0
    drop, at = 0.0, 0
    for fc in range(15000, 20750, 250):
        lo = rel[(f >= fc - 750) & (f < fc - 250)].mean()
        hi = rel[(f >= fc + 250) & (f < fc + 750)].mean()
        if lo - hi > drop:
            drop, at = float(lo - hi), fc
    return cutoff, drop, at


def info(path):
    m = mutagen.File(path)
    i = m.info if m else None
    ext = os.path.splitext(path)[1].lower()
    codec = type(m).__name__.lower() if m else "?"
    lossless = ext in LOSSLESS_EXT or "alac" in str(getattr(i, "codec", "")).lower()
    return dict(dur=float(getattr(i, "length", 0) or 0), sr=int(getattr(i, "sample_rate", 44100) or 44100),
                kbps=int((getattr(i, "bitrate", 0) or 0) / 1000), bits=getattr(i, "bits_per_sample", 0) or 0,
                lossless=lossless, codec=codec)


def source_guess(at):
    return "~128 kbps MP3" if at < 17000 else "~160-256 kbps MP3/AAC" if at < 19250 else "~320 kbps MP3 / 256 AAC"


def verdict(meta, cut, drop, at):
    k, ak = cut / 1000, at / 1000
    cliff = drop >= 15
    if meta["lossless"]:
        if cliff:
            return "FAKE", f"lossless file, but a {drop:.0f} dB encoder cliff at {ak:.1f} kHz = made from a {source_guess(at)}"
        if meta["sr"] > 48000 and 20500 <= cut < 23000:
            return "CHECK", f"hi-res {meta['sr']//1000} kHz file but content stops at {k:.1f} kHz - likely upsampled from CD quality"
        if drop >= 12:
            return "CHECK", f"{drop:.0f} dB drop at {ak:.1f} kHz - may be a lossy source; listen or view a spectrogram"
        if cut < 19000:
            return "CHECK", f"content stops at {k:.1f} kHz but rolls off gradually - a dark master or a lossy source; listen"
        return "OK", f"real lossless (content to {k:.1f} kHz, no encoder cliff)"
    kb = meta["kbps"]
    if kb and kb < 256:
        return "LOW", f"{kb} kbps lossy - not club quality"
    if cliff and at < 17500:
        return "FAKE", f"claims {kb} kbps but has a cliff at {ak:.1f} kHz = upscaled from ~128 kbps"
    if cliff and at < 19000:
        return "SUSPECT", f"claims {kb} kbps but has a cliff at {ak:.1f} kHz = probably upscaled from 160-192 kbps"
    return "OK", f"{kb} kbps, spectrum as expected (to {k:.1f} kHz)"


def check(path):
    try:
        meta = info(path)
        sr = 96000 if meta["sr"] > 48000 else 44100
        d = meta["dur"]
        starts = [max(0, d * q - 4) for q in (0.3, 0.5, 0.7)] if d > 30 else [0]
        specs = [s for s in (window_spectrum(path, st, sr) for st in starts) if s]
        if not specs:
            return dict(path=path, verdict="ERROR", why="could not decode / silent", cutoff=0, **meta)
        f = specs[0][0]
        rel = np.median(np.array([s[1] for s in specs]), 0)   # median across windows: robust to one odd section
        cut, drop, at = analyse_spectrum(f, rel)
        v, why = verdict(meta, cut, drop, at)
        return dict(path=path, verdict=v, why=why, cutoff=cut, cliff_db=round(drop, 1), cliff_khz=at / 1000, **meta)
    except Exception as e:
        return dict(path=path, verdict="ERROR", why=repr(e)[:120], cutoff=0)


def tag(path, text):
    m = mutagen.File(path)
    if m is None:
        return False
    if m.tags is None:
        m.add_tags()
    tags = m.tags
    if hasattr(tags, "getall"):  # ID3 (mp3, wav, aiff)
        from mutagen.id3 import COMM
        old = [c for c in tags.getall("COMM") if c.desc == ""]
        prev = str(old[0].text[0]) if old and old[0].text else ""
        prev = " | ".join(p for p in prev.split(" | ") if not p.startswith("AUDIOCHECK:"))
        tags.delall("COMM")
        tags.add(COMM(encoding=3, lang="eng", desc="", text=(prev + " | " if prev else "") + text))
    elif "\xa9cmt" in tags or path.lower().endswith(".m4a"):
        prev = " | ".join(p for p in (tags.get("\xa9cmt", [""])[0]).split(" | ") if not p.startswith("AUDIOCHECK:"))
        tags["\xa9cmt"] = [(prev + " | " if prev else "") + text]
    else:  # Vorbis comments (flac, ogg)
        prev = " | ".join(p for p in (tags.get("comment", [""])[0]).split(" | ") if not p.startswith("AUDIOCHECK:"))
        tags["comment"] = [(prev + " | " if prev else "") + text]
    m.save()
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--tag", action="store_true")
    ap.add_argument("--protect", nargs="*", default=[])
    ap.add_argument("--out", default=os.path.expanduser("~/.claude/dj-toolkit/runs"))
    ap.add_argument("--jobs", type=int, default=max(2, (os.cpu_count() or 4) - 1))
    a = ap.parse_args()
    files = []
    for p in a.paths:
        p = os.path.expanduser(p)
        if os.path.isdir(p):
            for root, _, names in os.walk(p):
                files += [os.path.join(root, n) for n in sorted(names) if n.lower().endswith(AUDIO) and not n.startswith("._")]
        elif os.path.isfile(p):
            files.append(p)
    if not files:
        sys.exit("no audio files found")
    print(f"checking {len(files)} files...", file=sys.stderr)
    rows, done = [], 0
    with ThreadPoolExecutor(a.jobs) as ex:
        for r in ex.map(check, files):
            rows.append(r); done += 1
            if done % 25 == 0:
                print(f"  {done}/{len(files)}", file=sys.stderr)
    order = {"FAKE": 0, "SUSPECT": 1, "CHECK": 2, "LOW": 3, "ERROR": 4, "OK": 5}
    rows.sort(key=lambda r: (order[r["verdict"]], r["path"]))

    protect = [os.path.abspath(os.path.expanduser(p)).rstrip(os.sep) + os.sep for p in a.protect]
    tagged = skipped = 0
    if a.tag:
        for r in rows:
            if r["verdict"] == "ERROR":
                continue
            if any(os.path.abspath(r["path"]).startswith(p) for p in protect):
                skipped += 1; continue
            try:
                tagged += tag(r["path"], f"AUDIOCHECK: {r['verdict']} ({r['cutoff']/1000:.1f} kHz)")
            except Exception as e:
                r["why"] += f" [tag failed: {e!r}]"[:80]

    os.makedirs(a.out, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d_%H%M%S")
    txt, csvp = os.path.join(a.out, f"audiocheck-report-{stamp}.txt"), os.path.join(a.out, f"audiocheck-report-{stamp}.csv")
    counts = {k: sum(r["verdict"] == k for r in rows) for k in order}
    with open(txt, "w", encoding="utf-8") as f:
        f.write(f"audiocheck report {stamp}\n{len(rows)} files: " + " · ".join(f"{k} {v}" for k, v in counts.items() if v) + "\n\n")
        for r in rows:
            f.write(f"{r['verdict']:<8} {r.get('why','')}\n         {r['path']}\n")
    with open(csvp, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["verdict", "cutoff_khz", "format", "kbps", "sample_rate", "bits", "seconds", "why", "path"])
        for r in rows:
            w.writerow([r["verdict"], round(r.get("cutoff", 0) / 1000, 1), "lossless" if r.get("lossless") else "lossy",
                        r.get("kbps", ""), r.get("sr", ""), r.get("bits", ""), round(r.get("dur", 0)), r.get("why", ""), r["path"]])
    print(" · ".join(f"{k} {v}" for k, v in counts.items() if v))
    for r in rows:
        if r["verdict"] in ("FAKE", "SUSPECT", "CHECK", "ERROR"):
            print(f"{r['verdict']:<8} {os.path.basename(r['path'])}  - {r['why']}")
    if a.tag:
        print(f"tagged {tagged} files" + (f", skipped {skipped} in protected folders" if skipped else ""))
    print(f"report: {txt}\ncsv:    {csvp}")


if __name__ == "__main__":
    main()
