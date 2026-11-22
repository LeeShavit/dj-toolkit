#!/usr/bin/env python3
"""Report format, length and bitrate for audio files, and flag suspicious ones.

usage: check_audio.py FILE_OR_DIR [...] [--json]
Uses ffprobe if installed, else macOS afinfo.
"""
import json, os, re, shutil, subprocess, sys

AUDIO = (".flac", ".mp3", ".wav", ".aif", ".aiff", ".m4a", ".alac", ".ogg", ".opus", ".webm")


def probe(path):
    if shutil.which("ffprobe"):
        out = subprocess.run(["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", path],
                             capture_output=True, text=True).stdout
        d = json.loads(out or "{}")
        fmt, st = d.get("format", {}), next((s for s in d.get("streams", []) if s.get("codec_type") == "audio"), {})
        return {"codec": st.get("codec_name"), "duration": float(fmt.get("duration") or 0),
                "bitrate": int(fmt.get("bit_rate") or 0), "sample_rate": int(st.get("sample_rate") or 0),
                "bits": int(st.get("bits_per_raw_sample") or st.get("bits_per_sample") or 0)}
    if shutil.which("afinfo"):
        out = subprocess.run(["afinfo", path], capture_output=True, text=True).stdout
        dur = re.search(r"estimated duration: ([\d.]+)", out)
        br = re.search(r"bit rate: (\d+)", out)
        sr = re.search(r"(\d+) Hz", out)
        return {"codec": os.path.splitext(path)[1][1:].lower(), "duration": float(dur.group(1)) if dur else 0,
                "bitrate": int(br.group(1)) if br else 0, "sample_rate": int(sr.group(1)) if sr else 0, "bits": 0}
    sys.exit("Need ffprobe (ffmpeg) or macOS afinfo")


def flags(path, p):
    f, ext = [], os.path.splitext(path)[1].lower()
    lossless = ext in (".flac", ".wav", ".aif", ".aiff", ".alac") or p["codec"] in ("flac", "alac", "pcm_s16le", "pcm_s24le")
    kbps = p["bitrate"] / 1000
    if lossless and ext == ".flac" and 0 < kbps < 500:
        f.append("FLAC bitrate low - possible transcode")
    if not lossless and 0 < kbps < 300:
        f.append(f"lossy {kbps:.0f} kbps")
    name = os.path.basename(path).lower()
    if "extended" in name and 0 < p["duration"] < 210:
        f.append("labelled extended but under 3:30")
    if re.search(r"\b(radio|short)\s*edit\b", name):
        f.append("radio/short edit")
    elif re.search(r"\bedit\b", name) and "extended" not in name:
        f.append("an edit - check it's the wanted version")
    return lossless, f


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    as_json = "--json" in sys.argv
    files = []
    for a in args:
        a = os.path.expanduser(a)
        if os.path.isdir(a):
            for root, _, names in os.walk(a):
                files += [os.path.join(root, n) for n in sorted(names) if n.lower().endswith(AUDIO)]
        elif os.path.exists(a):
            files.append(a)
    rows = []
    for path in files:
        p = probe(path)
        lossless, f = flags(path, p)
        rows.append({"file": path, "lossless": lossless, "length": f"{int(p['duration'] // 60)}:{int(p['duration'] % 60):02d}",
                     "kbps": round(p["bitrate"] / 1000), **p, "flags": f})
    if as_json:
        print(json.dumps(rows, indent=1, ensure_ascii=False))
    else:
        for r in rows:
            q = "LOSSLESS" if r["lossless"] else f"{r['kbps']}k"
            print(f"{r['length']:>6}  {q:>8}  {'⚠ ' + '; '.join(r['flags']) if r['flags'] else 'ok':<40}  {os.path.basename(r['file'])}")


if __name__ == "__main__":
    main()
