# /// script
# dependencies = [
#   "certifi",
# ]
# ///
"""Look up tracks on Deezer (artist + title only). Writes a resumable JSON cache; never touches audio files."""
import difflib, json, os, re, ssl, sys, time, urllib.parse, urllib.request
import certifi

S = os.environ["WORK"]
rows = json.load(open(f"{S}/scan.json"))
CACHE = f"{S}/deezer.json"
cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
CTX = ssl.create_default_context(cafile=certifi.where())
SKIP = tuple(p.strip("/") + "/" for p in os.environ.get("PROTECTED_REL", "").split(os.pathsep) if p)  # scan.py already skips protected folders
last = [0.0]

def get(url):
    for attempt in range(5):
        wait = 0.22 - (time.time() - last[0])
        if wait > 0:
            time.sleep(wait)
        last[0] = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "dj-library-organizer/1.0"})
            with urllib.request.urlopen(req, timeout=20, context=CTX) as r:
                d = json.load(r)
            if isinstance(d, dict) and d.get("error"):
                if d["error"].get("code") == 4:  # quota
                    time.sleep(6)
                    continue
                return {}
            return d
        except Exception:
            time.sleep(2 * (attempt + 1))
    return {}

def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()

def base_title(t):
    t = re.sub(r"\s*[\(\[].*?[\)\]]", "", t)
    return re.sub(r"\s+-\s+.*$", "", t).strip()

def parts(r):
    t = r.get("tags", {})
    name = os.path.splitext(os.path.basename(r["path"]))[0]
    artist, title = t.get("artist"), t.get("title")
    if not title:
        m = re.match(r"(.+?) - (.+)", name)
        if m and not artist:
            artist, title = m.group(1), m.group(2)
        elif m:
            title = m.group(2)
        else:
            title = name
    return (artist or "").strip(), title.strip()

def score(a, t, length, c):
    ca = norm(c.get("artist", {}).get("name"))
    first = norm(re.split(r",|&| feat| ft\b| x ", a, flags=re.I)[0])
    a_ok = first and (first in ca or ca in norm(a) or difflib.SequenceMatcher(None, first, ca).ratio() > .8)
    ts = max(difflib.SequenceMatcher(None, norm(t), norm(c.get("title"))).ratio(),
             difflib.SequenceMatcher(None, norm(t), norm(c.get("title_short"))).ratio())
    dd = abs((c.get("duration") or 0) - (length or 0))
    return (1 if a_ok else 0) * ts - min(dd, 60) / 200, ts, dd, bool(a_ok)

def search(q):
    return (get("https://api.deezer.com/search?limit=15&q=" + urllib.parse.quote(q)) or {}).get("data", [])

todo = [r for r in rows if not (SKIP and r["path"].startswith(SKIP)) and r["path"] not in cache]
print("todo", len(todo), flush=True)
for n, r in enumerate(todo):
    a, t = parts(r)
    first = re.split(r",|&| feat| ft\b", a, flags=re.I)[0].strip()
    cands = []
    if first:
        cands = search(f'artist:"{first}" track:"{base_title(t)}"')
    if not cands:
        cands = search(f"{first} {base_title(t)}".strip())
    best = None
    if cands:
        best = max(cands, key=lambda c: score(a, t, r.get("length"), c)[0])
    out = {"query": [a, t]}
    if best:
        s, ts, dd, a_ok = score(a, t, r.get("length"), best)
        out.update(score=round(s, 3), title_sim=round(ts, 3), dur_diff=dd, artist_ok=a_ok)
        tr = get(f"https://api.deezer.com/track/{best['id']}") or {}
        al = get(f"https://api.deezer.com/album/{best['album']['id']}") or {}
        out.update(deezer_id=best["id"], title=tr.get("title"), artist=best["artist"]["name"],
                   contributors=[c["name"] for c in tr.get("contributors", [])],
                   isrc=tr.get("isrc"), bpm=tr.get("bpm"), gain=tr.get("gain"), release=tr.get("release_date"),
                   album=al.get("title"), label=al.get("label"), upc=al.get("upc"),
                   genres=[g["name"] for g in al.get("genres", {}).get("data", [])],
                   track_pos=tr.get("track_position"), disc=tr.get("disk_number"),
                   explicit=tr.get("explicit_lyrics"), cover=al.get("cover_xl"))
    cache[r["path"]] = out
    if n % 20 == 0:
        json.dump(cache, open(CACHE, "w"), ensure_ascii=False)
        print(n, a[:30], "|", t[:40], "->", out.get("score"), flush=True)
json.dump(cache, open(CACHE, "w"), ensure_ascii=False)
print("done", len(cache))
