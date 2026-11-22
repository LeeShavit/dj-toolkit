#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["mutagen"]
# ///
"""Check downloaded "extended" files against what find_extended.py asked for.

Downloaders often save the radio edit under the extended name (62 of 364 in a real run),
so the filename proves nothing - the LENGTH does.

usage: uv run verify_downloads.py MATCHES_JSON DOWNLOAD_DIR [DOWNLOAD_DIR ...] [--since "YYYY-MM-DD HH:MM"]
Writes verify.csv next to MATCHES_JSON and prints a summary.
  OK         length >= max(old + 45 s, 4:00) and within 15 s of the expected extended length (if known)
  TOO-SHORT  probably the radio edit saved under the extended name
  CHECK      long enough, but differs > 15 s from the expected length (maybe another mix)
  MISSING    no downloaded file matches this song
"""
import csv, json, os, re, sys, time, unicodedata
from difflib import SequenceMatcher
import mutagen

AUD = (".flac", ".mp3", ".wav", ".aif", ".aiff", ".m4a")


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower().replace("&", " and ")
    s = re.sub(r"\b(feat|ft)\.?\b.*?(?=[\(\[\-]|$)", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    since = None
    if "--since" in sys.argv:
        since = time.mktime(time.strptime(sys.argv[sys.argv.index("--since") + 1], "%Y-%m-%d %H:%M"))
        args = [a for a in args if a != sys.argv[sys.argv.index("--since") + 1]]
    matches = json.load(open(args[0]))
    files = []
    for d in args[1:]:
        for root, _, names in os.walk(os.path.expanduser(d)):
            for n in names:
                p = os.path.join(root, n)
                if n.lower().endswith(AUD) and not n.startswith("._") and (not since or os.path.getmtime(p) >= since):
                    files.append(p)
    pool = [(p, norm(os.path.splitext(os.path.basename(p))[0])) for p in files]
    rows, used = [], set()
    for r in matches:
        m = r.get("match")
        if r["status"] not in ("found", "review") or not m:
            continue
        want = norm(f"{m['artist']} {m['title']} {m.get('ver', '')}")
        base = norm(r["base"])
        best, bs = None, 0.0
        for p, n in pool:
            if p in used or base not in n:
                continue
            s = SequenceMatcher(None, n, want).ratio()
            if s > bs:
                best, bs = p, s
        if not best:
            rows.append(dict(song=f"{r['artist']} - {r['title']}", wanted=m["title"], status="MISSING", file="", length="", old=r["dur"]))
            continue
        used.add(best)
        length = mutagen.File(best).info.length
        need = max(r["dur"] + 45, 240)
        exp = m.get("dur") or 0
        st = "TOO-SHORT" if length < need else ("CHECK" if exp and abs(length - exp) > 15 else "OK")
        rows.append(dict(song=f"{r['artist']} - {r['title']}", wanted=m["title"], status=st, file=best,
                         length=round(length), old=r["dur"], expected=exp))
    out = os.path.join(os.path.dirname(os.path.abspath(args[0])), "verify.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["status", "song", "wanted", "length", "old", "expected", "file"], extrasaction="ignore")
        w.writeheader(); w.writerows(sorted(rows, key=lambda x: x["status"]))
    c = {s: sum(x["status"] == s for x in rows) for s in ("OK", "TOO-SHORT", "CHECK", "MISSING")}
    print(" · ".join(f"{k} {v}" for k, v in c.items()))
    fmt = lambda s: f"{int(s)//60}:{int(s)%60:02d}" if s != "" else "-"
    for x in rows:
        if x["status"] in ("TOO-SHORT", "CHECK"):
            print(f"{x['status']:<9} {x['song'][:55]:55} got {fmt(x['length'])} (old {fmt(x['old'])}, expected {fmt(x.get('expected') or '')})")
    print("written:", out)


if __name__ == "__main__":
    main()
