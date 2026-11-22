# /// script
# dependencies = [
#   "mutagen",
# ]
# ///
"""Read-only scan of audio files: tags, stream info, content fingerprint of first 1MB."""
import collections, hashlib, json, os, sys
from mutagen import File as MF
from mutagen.id3 import ID3

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
OUT = sys.argv[1]
EXT = {".flac", ".mp3", ".wav", ".aiff", ".aif", ".m4a"}
ID3MAP = {"TIT2": "title", "TPE1": "artist", "TALB": "album", "TCON": "genre", "TBPM": "bpm",
          "TKEY": "key", "TPUB": "label", "TPE4": "remixer", "TDRC": "year", "TSRC": "isrc"}
VC = {"title": "title", "artist": "artist", "album": "album", "genre": "genre", "bpm": "bpm",
      "tempo": "bpm", "initialkey": "key", "key": "key", "label": "label", "organization": "label",
      "publisher": "label", "remixer": "remixer", "mixartist": "remixer", "date": "year", "year": "year",
      "isrc": "isrc", "comment": "comment", "description": "comment"}
rows = []
for dp, dn, fn in os.walk(os.path.expanduser(os.environ.get("SCAN_DIR", ROOT))):
    dn[:] = [d for d in dn if not is_protected(os.path.relpath(os.path.join(dp, d), ROOT))]
    for f in fn:
        if os.path.splitext(f)[1].lower() not in EXT:
            continue
        p = os.path.join(dp, f)
        r = {"path": os.path.relpath(p, ROOT), "ext": os.path.splitext(f)[1].lower(), "size": os.path.getsize(p)}
        try:
            with open(p, "rb") as fh:
                fh.seek(max(0, r["size"] // 2))
                r["midhash"] = hashlib.md5(fh.read(1 << 20)).hexdigest()
            a = MF(p)
            if a is None:
                r["error"] = "unrecognized"
            else:
                i = a.info
                r.update(length=round(getattr(i, "length", 0) or 0, 1), bitrate=getattr(i, "bitrate", None),
                         sr=getattr(i, "sample_rate", None), bits=getattr(i, "bits_per_sample", None))
                t = {}
                tags = a.tags
                if tags is not None:
                    if isinstance(tags, ID3):
                        for k, v in ID3MAP.items():
                            if k in tags:
                                t[v] = str(tags[k].text[0]) if getattr(tags[k], "text", None) else ""
                        c = tags.getall("COMM")
                        if c:
                            t["comment"] = str(c[0].text[0]) if c[0].text else ""
                        r["art"] = bool(tags.getall("APIC"))
                    else:
                        for k, v in tags.items():
                            k = k.lower()
                            if k in VC and v:
                                t[VC[k]] = str(v[0])
                        r["art"] = bool(getattr(a, "pictures", None))
                r["tags"] = {k: v for k, v in t.items() if str(v).strip()}
        except Exception as e:
            r["error"] = repr(e)[:200]
        rows.append(r)
json.dump(rows, open(OUT, "w"), ensure_ascii=False, indent=0)

top = collections.Counter()
print("files", len(rows), "errors", sum("error" in r for r in rows))
for r in rows:
    if "error" in r:
        print(" ERR", r["path"], r["error"])
print("ext", collections.Counter(r["ext"] for r in rows))
for fld in "title artist album genre bpm key label remixer year isrc comment".split():
    print(f"{fld:8} {sum(fld in r.get('tags', {}) for r in rows):4}/{len(rows)}")
print("art", sum(bool(r.get("art")) for r in rows))
print("top genres", collections.Counter(r.get("tags", {}).get("genre") for r in rows).most_common(25))
print("sr", collections.Counter((r.get("sr"), r.get("bits")) for r in rows).most_common(10))
print("low-bitrate mp3", sum(1 for r in rows if r["ext"] == ".mp3" and (r.get("bitrate") or 0) < 256000))
g = collections.defaultdict(list)
for r in rows:
    g[(r["size"], r["midhash"])].append(r["path"])
d = [v for v in g.values() if len(v) > 1]
print("exact-dupe groups", len(d), "extra copies", sum(len(v) - 1 for v in d))
for v in d[:40]:
    print("  ", v)
print("--- sample")
for r in rows[::60]:
    print(r["path"][:90], "|", json.dumps(r.get("tags"), ensure_ascii=False)[:200])
