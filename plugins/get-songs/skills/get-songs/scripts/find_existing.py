#!/usr/bin/env python3
"""Check which tracks in a list already exist in the user's folders.

usage: find_existing.py LIST_FILE FOLDER [FOLDER ...] [--json]
LIST_FILE: one "Artist - Title (Version)" per line (or a CSV with Artist,Title columns).
For each track prints: HAVE (same version), OTHER-VERSION (same song, different version), or MISSING.
"""
import csv, json, os, re, sys, unicodedata

AUDIO = (".flac", ".mp3", ".wav", ".aif", ".aiff", ".m4a", ".alac", ".ogg", ".opus")
VERSION_WORDS = {"extended", "radio", "edit", "club", "remix", "dub", "instrumental", "vip", "rework", "original", "mix", "version"}


def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(feat|ft|featuring)\.?\b.*?(?=[\(\[\-]|$)", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return s.split()


def split_track(line):
    m = re.match(r"\s*(.+?)\s+[-–]\s+(.+)", line)
    artist, title = (m.group(1), m.group(2)) if m else ("", line)
    base = re.sub(r"[\(\[].*?[\)\]]", " ", title)
    version = " ".join(re.findall(r"[\(\[](.*?)[\)\]]", title))
    return artist, base, version


def read_list(path):
    if path.lower().endswith(".csv"):
        with open(path, encoding="utf-8") as f:
            return [f"{r.get('Artist', '')} - {r.get('Title', '')}" for r in csv.DictReader(f)]
    return [l.strip() for l in open(path, encoding="utf-8") if l.strip()]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    tracks, folders = read_list(os.path.expanduser(args[0])), [os.path.expanduser(a) for a in args[1:]]
    files = []
    for d in folders:
        for root, _, names in os.walk(d):
            if "/_rejected" in root:
                continue
            files += [(os.path.join(root, n), set(norm(os.path.splitext(n)[0]))) for n in names if n.lower().endswith(AUDIO)]
    out = []
    for t in tracks:
        artist, base, version = split_track(t)
        a_tok = [w for w in norm(artist) if len(w) > 1][:2]           # first artist words
        b_tok = [w for w in norm(base) if w not in VERSION_WORDS]
        v_tok = [w for w in norm(version) if w not in {"mix", "version"}]
        have, other = [], []
        for path, toks in files:
            if b_tok and all(w in toks for w in b_tok) and (not a_tok or any(w in toks for w in a_tok)):
                (have if all(w in toks for w in v_tok) else other).append(path)
        status = "HAVE" if have else "OTHER-VERSION" if other else "MISSING"
        out.append({"track": t, "status": status, "matches": (have or other)[:3]})
    if "--json" in sys.argv:
        print(json.dumps(out, indent=1, ensure_ascii=False))
    else:
        for r in out:
            print(f"{r['status']:<14} {r['track']}" + (f"\n{'':15}→ {r['matches'][0]}" if r["matches"] else ""))
        c = {s: sum(r["status"] == s for r in out) for s in ("HAVE", "OTHER-VERSION", "MISSING")}
        print(f"\n{c['HAVE']} have · {c['OTHER-VERSION']} other version · {c['MISSING']} missing")


if __name__ == "__main__":
    main()
