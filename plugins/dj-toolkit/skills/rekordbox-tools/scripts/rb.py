#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyrekordbox>=0.4", "mutagen", "imageio-ffmpeg>=0.5"]
# ///
"""rekordbox 6/7 database tools (via pyrekordbox). Read commands work while rekordbox runs;
write commands need rekordbox AND its background agent fully quit.

  status [--db PATH]                          collection size, missing files, needs-analysis, playlists
  missing [--db PATH]                         list tracks whose file is gone
  bpm [--db PATH] [--folder TEXT]             BPM triage: near-whole BPMs that will drift vs real decimals
  map --old-root DIR --new-root DIR -o map.csv
                                              propose old->new file pairs for tracks under old-root
                                              (same genre subfolder, same core title/artist)
  plan --map map.csv -o plan.csv [--allow-shorter]
                                              classify each pair: repoint (identical audio: keeps cues/grid),
                                              swap (new audio: resets analysis + cues), merge (two entries
                                              -> one file), skip (new file shorter / missing)
  apply --plan plan.csv [--db PATH] [--yes]   write it. Backs up master.db first. --db = test on a COPY.

Test first:  mkdir t && cp ~/Library/Pioneer/rekordbox/master.db* t/ && rb.py apply --plan plan.csv --db t/master.db
"""
import argparse, csv, datetime, hashlib, os, re, shutil, subprocess, sys, unicodedata
from difflib import SequenceMatcher

AUD = (".mp3", ".flac", ".wav", ".aiff", ".aif", ".m4a", ".ogg")
FILETYPE = {".mp3": 1, ".m4a": 4, ".flac": 5, ".wav": 11, ".aif": 12, ".aiff": 12}


def db_open(path=None):
    try:
        from pyrekordbox.masterdb import MasterDatabase as DB      # pyrekordbox >= 0.5
    except ImportError:
        from pyrekordbox import Rekordbox6Database as DB             # older releases
    return DB(path=path) if path else DB()


def db_dir():
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Pioneer/rekordbox")
    return os.path.join(os.environ.get("APPDATA", ""), "Pioneer", "rekordbox")


def rekordbox_running():
    try:
        if sys.platform == "win32":
            out = subprocess.run(["tasklist"], capture_output=True, text=True).stdout.lower()
            return "rekordbox" in out
        return subprocess.run(["pgrep", "-if", "rekordbox"], capture_output=True).returncode == 0
    except Exception:
        return False


def norm(s):
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower())


def core(stem):
    """artist + title without bracketed mix info / ' - Mix' suffix."""
    artist, _, title = stem.partition(" - ")
    title = re.split(r"\s+-\s+", title)[0]
    title = re.sub(r"\s*[\(\[].*$", "", title)
    return norm(re.split(r",|&| x | feat", artist)[0]), norm(title)


def audio_md5(path, seconds=60):
    ff = shutil.which("ffmpeg") or __import__("imageio_ffmpeg").get_ffmpeg_exe()
    r = subprocess.run([ff, "-v", "quiet", "-t", str(seconds), "-i", path, "-f", "s16le", "-ac", "2", "-ar", "44100", "-"],
                       capture_output=True)
    return hashlib.md5(r.stdout).hexdigest() if r.stdout else None


def length(path):
    import mutagen
    m = mutagen.File(path)
    return float(m.info.length) if m else 0.0


# ---------------------------------------------------------------- read-only commands
def cmd_status(a):
    db = db_open(a.db)
    cs = db.get_content().all()
    roots = {}
    for c in cs:
        p = c.FolderPath or ""
        top = os.sep.join(p.split(os.sep)[:5]) if p else "(none)"
        roots[top] = roots.get(top, 0) + 1
    print(f"tracks: {len(cs)} | missing files: {sum(1 for c in cs if c.FolderPath and not os.path.exists(c.FolderPath))}"
          f" | needs analysis: {sum(1 for c in cs if not c.Analysed)}")
    print(f"playlists: {db.get_playlist().count()} | playlist entries: {db.get_playlist_songs().count()}")
    print("tracks by location:")
    for k, v in sorted(roots.items(), key=lambda kv: -kv[1])[:12]:
        print(f"  {v:5}  {k}")


def cmd_missing(a):
    db = db_open(a.db)
    for c in db.get_content().all():
        if c.FolderPath and not os.path.exists(c.FolderPath):
            print(f"{c.ID}\t{c.FolderPath}")


def cmd_bpm(a):
    db = db_open(a.db)
    whole, decimal = [], []
    for c in db.get_content().all():
        if not c.BPM or (a.folder and a.folder not in (c.FolderPath or "")):
            continue
        bpm = c.BPM / 100
        frac = abs(bpm - round(bpm))
        if frac == 0:
            continue
        (whole if frac <= 0.05 else decimal).append((bpm, c.Title or "", c.FolderPath or ""))
    print(f"## {len(whole)} near-whole BPMs (true tempo is the rounded value - the grid will drift; fix the grid)")
    for b, t, p in sorted(whole):
        print(f"  {b:7.2f} -> {round(b):3d}  {t[:60]}")
    print(f"\n## {len(decimal)} real decimal BPMs (often vinyl/tape-era or live-played; leave them, or warp in software)")
    for b, t, p in sorted(decimal):
        print(f"  {b:7.2f}         {t[:60]}")


# ---------------------------------------------------------------- map / plan / apply
def cmd_map(a):
    old_root = os.path.abspath(os.path.expanduser(a.old_root)).rstrip(os.sep) + os.sep
    new_root = os.path.abspath(os.path.expanduser(a.new_root)).rstrip(os.sep) + os.sep
    new = {}
    for r, _, ns in os.walk(new_root):
        for n in ns:
            if n.lower().endswith(AUD) and not n.startswith("."):
                rel_dir = os.path.relpath(r, new_root)
                new.setdefault(rel_dir, []).append(os.path.join(r, n))
    all_new = [p for v in new.values() for p in v]
    db = db_open(a.db)
    rows = []
    for c in db.get_content().all():
        p = c.FolderPath or ""
        if not p.startswith(old_root):          # trailing separator: "Lib 9.11" is not inside "Lib"
            continue
        rel_dir = os.path.relpath(os.path.dirname(p), old_root)
        ca, ct = core(os.path.splitext(os.path.basename(p))[0])
        best, bs = "", 0.0
        for pool in (new.get(rel_dir, []), all_new):
            for q in pool:
                na, nt = core(os.path.splitext(os.path.basename(q))[0])
                if not nt or not ct:
                    continue
                s = SequenceMatcher(None, ct, nt).ratio() + (0.2 if ca and ca == na else 0)
                if s > bs:
                    best, bs = q, s
            if bs >= 1.1:
                break
        rows.append(dict(id=c.ID, old=p, new=best if bs >= 1.0 else "", confidence=round(bs, 2), title=c.Title or ""))
    with open(a.o, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "title", "old", "new", "confidence"]); w.writeheader(); w.writerows(rows)
    print(f"{len(rows)} tracks under old root, {sum(1 for r in rows if r['new'])} mapped -> {a.o}")
    print("Review low-confidence rows (< 1.15) and fix 'new' by hand before planning. A curated list "
          "(e.g. upgrade-to-extended's matches) beats fuzzy matching.")


def cmd_plan(a):
    rows = [r for r in csv.DictReader(open(a.map)) if r.get("new")]
    by_new = {}
    for r in rows:
        by_new.setdefault(r["new"], []).append(r)
    out = []
    for new, rs in by_new.items():
        if not os.path.exists(new):
            out += [dict(action="skip", reason="new file missing", **r) for r in rs]; continue
        nmd5, nlen = audio_md5(new), length(new)
        info = []
        for r in rs:
            same = os.path.exists(r["old"]) and audio_md5(r["old"]) == nmd5
            info.append((r, same, length(r["old"]) if os.path.exists(r["old"]) else 0))
        info.sort(key=lambda x: not x[1])                                   # identical-audio entry wins
        primary, same, olen = info[0]
        if same:
            out.append(dict(action="repoint", reason="identical audio - keeps cues/grid", **primary))
        elif nlen + 1 < olen and not a.allow_shorter:
            out.append(dict(action="skip", reason=f"new file shorter ({nlen:.0f}s < {olen:.0f}s)", **primary))
        else:
            out.append(dict(action="swap", reason=f"new audio {olen:.0f}s -> {nlen:.0f}s: resets analysis + cues", **primary))
        for r, _, _ in info[1:]:
            out.append(dict(action="merge", reason=f"duplicate entry -> merged into {primary['id']}", into=primary["id"], **r))
    with open(a.o, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["action", "reason", "id", "title", "old", "new", "into", "confidence"], extrasaction="ignore")
        w.writeheader(); w.writerows(out)
    from collections import Counter
    print(dict(Counter(r["action"] for r in out)), "->", a.o)


def set_file(c, path):
    import mutagen
    m = mutagen.File(path); i = m.info
    c.FolderPath = path; c.FileNameL = os.path.basename(path); c.FileSize = os.path.getsize(path)
    c.FileType = FILETYPE.get(os.path.splitext(path)[1].lower(), c.FileType)
    c.Length = int(round(i.length))
    c.SampleRate = getattr(i, "sample_rate", c.SampleRate) or c.SampleRate
    c.BitDepth = getattr(i, "bits_per_sample", 0) or c.BitDepth
    c.BitRate = int(getattr(i, "bitrate", 0) / 1000) if path.lower().endswith((".mp3", ".m4a")) else 0


def cmd_apply(a):
    plan = list(csv.DictReader(open(a.plan)))
    work = [r for r in plan if r["action"] in ("repoint", "swap", "merge")]
    if not a.db and rekordbox_running():
        sys.exit("rekordbox (or its agent) is running - quit it fully first.")
    print(f"{sum(r['action']=='repoint' for r in work)} repoint, {sum(r['action']=='swap' for r in work)} swap, "
          f"{sum(r['action']=='merge' for r in work)} merge" + (f"  [TEST COPY {a.db}]" if a.db else "  [LIVE DATABASE]"))
    if not a.yes:
        if input("type 'yes' to write: ").strip() != "yes":
            sys.exit("cancelled")
    if not a.db:
        bk = os.path.expanduser(f"~/.claude/dj-toolkit/backups/rekordbox-db-{datetime.datetime.now():%Y%m%d-%H%M%S}")
        os.makedirs(bk)
        for f in ("master.db", "master.db-wal", "master.db-shm"):
            if os.path.exists(os.path.join(db_dir(), f)):
                shutil.copy2(os.path.join(db_dir(), f), bk)
        shutil.copy2(a.plan, bk)
        print("backup:", bk)
    db = db_open(a.db)
    cues = 0
    for r in work:
        c = db.get_content(ID=r["id"])
        if c is None:
            print("  not found:", r["id"], r["old"]); continue
        if r["action"] == "repoint":
            set_file(c, r["new"])
        elif r["action"] == "swap":
            set_file(c, r["new"])
            st = os.path.splitext(os.path.basename(r["new"]))[0]
            if " - " in st:
                c.Title = st.split(" - ", 1)[1]
            c.Analysed = 0; c.BPM = 0
            for cue in db.get_cue(ContentID=c.ID).all():
                db.delete(cue); cues += 1
        elif r["action"] == "merge":
            have = {sp.PlaylistID for sp in db.get_playlist_songs(ContentID=r["into"]).all()}
            for sp in db.get_playlist_songs(ContentID=c.ID).all():
                if sp.PlaylistID in have:
                    db.delete(sp)
                else:
                    sp.ContentID = r["into"]; have.add(sp.PlaylistID)
    db.commit()
    print(f"done. cues removed on swapped tracks: {cues}")
    print("In rekordbox: select the swapped tracks -> Reload Tag, then Analyze Track; re-set hot cues on tracks that had them.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("status", "missing", "bpm", "map", "plan", "apply"):
        p = sub.add_parser(name)
        p.add_argument("--db", default=None, help="path to a COPY of master.db (testing)")
        if name == "bpm": p.add_argument("--folder", default="")
        if name == "map":
            p.add_argument("--old-root", required=True); p.add_argument("--new-root", required=True); p.add_argument("-o", default="map.csv")
        if name == "plan":
            p.add_argument("--map", required=True); p.add_argument("-o", default="plan.csv"); p.add_argument("--allow-shorter", action="store_true")
        if name == "apply":
            p.add_argument("--plan", required=True); p.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    globals()["cmd_" + a.cmd](a)


if __name__ == "__main__":
    main()
