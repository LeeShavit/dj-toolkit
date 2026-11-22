# /// script
# dependencies = [
#   "mutagen",
#   "certifi",
# ]
# ///
"""Apply plan.json: write tags, then move files. --test ROOT runs tags only on a sandbox copy."""
import json, os, re, ssl, sys, time, urllib.request
import certifi
from mutagen import File as MF
from mutagen.flac import FLAC, Picture
from mutagen.id3 import ID3, APIC, COMM, TALB, TBPM, TCON, TDRC, TIT2, TKEY, TPE1, TPE4, TPUB, TSRC, TXXX
from mutagen.wave import WAVE

S = os.environ["WORK"]
plan = json.load(open(f"{S}/plan.json"))
ROOT = os.path.expanduser(os.environ["MUSIC_ROOT"])


def _protected():
    """Folders no tool may touch: PROTECTED env (os.pathsep-separated, absolute or relative to MUSIC_ROOT)."""
    out = []
    for p in filter(None, os.environ.get("PROTECTED", "").split(os.pathsep)):
        p = os.path.expanduser(p)
        out.append(os.path.relpath(p, ROOT) if os.path.isabs(p) else p.strip("/"))
    return out


PROTECTED = _protected()


def is_protected(rel):
    """rel is relative to MUSIC_ROOT. Trailing-separator match: 'DJ Library 9.11' is NOT inside 'DJ Library'."""
    rel = rel.replace(os.sep, "/")
    return any(rel == p or rel.startswith(p.rstrip("/") + "/") for p in PROTECTED)


CTX = ssl.create_default_context(cafile=certifi.where())
TEXT = {"title": TIT2, "artist": TPE1, "album": TALB, "genre": TCON, "bpm": TBPM, "key": TKEY, "label": TPUB,
        "remixer": TPE4, "isrc": TSRC, "year": TDRC}
VORB = {"title": ["title"], "artist": ["artist"], "album": ["album"], "genre": ["genre"], "bpm": ["bpm"],
        "key": ["initialkey"], "label": ["label", "organization"], "remixer": ["remixer"], "isrc": ["isrc"],
        "year": ["date"], "barcode": ["barcode"]}

def clean_text(c):
    c = re.sub(r"\s*\|?\s*Downloaded with OfflineDJ - https://www\.OfflineDJ\.com\s*", "", c or "")
    return c.strip(" |")

def cover(url):
    with urllib.request.urlopen(url, timeout=20, context=CTX) as r:
        return r.read()

def tag_flac(path, new, art):
    a = FLAC(path)
    if a.tags is None:
        a.add_tags()
    for k, v in new.items():
        if k == "comment":
            continue
        names = VORB[k]
        # reuse a key the file already carries, e.g. "tempo" or "key"
        if k == "bpm" and "tempo" in a:
            names = ["tempo"]
        if k == "key" and "key" in a and "initialkey" not in a:
            names = ["key"]
        for n in names:
            a[n] = [str(v)]
    for n in ("comment", "description"):
        if n in a:
            vals = [clean_text(x) for x in a[n]]
            vals = [x for x in vals if x and not re.fullmatch(r"(\s*[0-9A-F]{8}){6,}\s*", x)]
            if vals:
                a[n] = vals
            else:
                del a[n]
    if art:
        p = Picture()
        p.type, p.mime, p.data = 3, "image/jpeg", art
        a.add_picture(p)
    a.save()

def tag_id3(path, new, art):
    a = MF(path)
    if a.tags is None:
        a.add_tags()
    tags = a.tags
    for k, v in new.items():
        if k == "barcode":
            tags.setall("TXXX:BARCODE", [TXXX(encoding=3, desc="BARCODE", text=[str(v)])])
        elif k != "comment":
            tags.setall(TEXT[k].__name__, [TEXT[k](encoding=3, text=[str(v)])])
    for fr in list(tags.getall("COMM")):
        if fr.desc.startswith("iTun"):
            continue
        t = clean_text(fr.text[0] if fr.text else "")
        tags.delall(fr.HashKey)
        if t:
            tags.add(COMM(encoding=3, lang=fr.lang, desc=fr.desc, text=[t]))
    if art:
        tags.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=art))
    v2 = 3 if getattr(tags, "version", (2, 4))[1] == 3 else 4
    a.save(v2_version=v2)

def write(path, p):
    art = cover(p["cover"]) if p.get("cover") else None
    (tag_flac if path.lower().endswith(".flac") else tag_id3)(path, p["new"], art)

if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--test":
        sb = sys.argv[2]
        for f in sorted(os.listdir(sb)):
            p = next(x for x in plan if os.path.basename(x["src"]) == f and x["new"])
            write(os.path.join(sb, f), p)
            a = MF(os.path.join(sb, f))
            print(f[:50], "->", {k: str(v)[:60] for k, v in a.tags.items() if k.lower() in (
                "genre", "isrc", "date", "label", "remixer", "bpm", "initialkey", "comment", "tcon", "tsrc", "tkey", "tbpm", "tpe4", "tpub", "tdrc")} if a.tags else None)
        sys.exit()

    # preflight: nothing overwrites anything
    for p in plan:
        assert not is_protected(p["src"]), ("protected", p["src"])
        assert not is_protected(p["dest"]), ("protected", p["dest"])
        assert os.path.exists(os.path.join(ROOT, p["src"])), p["src"]
        if p["dest"] != p["src"]:
            assert not os.path.exists(os.path.join(ROOT, p["dest"])), p["dest"]
    assert len({p["dest"] for p in plan}) == len(plan)

    errors, log = [], []
    for p in plan:
        if p["state"] == "quarantine":
            continue
        try:
            write(os.path.join(ROOT, p["src"]), p)
        except Exception as e:
            errors.append((p["src"], repr(e)[:200]))
    print("tag errors", len(errors), errors[:10])
    if errors:
        sys.exit("stopping before any move")
    for p in plan:
        if p["dest"] != p["src"]:
            d = os.path.join(ROOT, p["dest"])
            os.makedirs(os.path.dirname(d), exist_ok=True)
            os.rename(os.path.join(ROOT, p["src"]), d)
            log.append({"from": p["src"], "to": p["dest"]})
    json.dump(log, open(os.path.join(S, f"music_move_log_{time.strftime('%Y%m%d_%H%M%S')}.json"), "w"), ensure_ascii=False, indent=0)
    print("moved", len(log))
