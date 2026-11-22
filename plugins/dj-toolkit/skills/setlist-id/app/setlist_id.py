#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "yt-dlp>=2026.10",
#   "shazamio>=0.9",
#   "httpx>=0.28",
#   "certifi",
#   "imageio-ffmpeg>=0.6",
#   "deno>=2.5",
# ]
# ///
"""setlist-id: identify every track in a DJ set from a SoundCloud / YouTube link.

Pipeline:
  1. Download the set's audio with yt-dlp (or use a local file).
  2. Fingerprint a short clip every N seconds against Shazam.
  3. Merge consecutive hits into a tracklist (majority vote picks the version/remix).
  4. Resolve exact streaming links by ISRC (Apple Music, Deezer, Spotify) + search links.
  5. Write tracklist.html / tracklist.md / tracklist.json.
"""
from __future__ import annotations

import argparse
import asyncio
import difflib
import html
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
import urllib.parse
import uuid
import wave
import webbrowser
from pathlib import Path

import certifi

os.environ.setdefault("SSL_CERT_FILE", certifi.where())  # python.org builds ship without CA certs

import httpx
import yt_dlp
from shazamio import Shazam
from shazamio.converter import Converter
from shazamio.misc import ShazamUrl

ROOT = Path(__file__).resolve().parent
# Standalone app: data lives next to the script. As a plugin skill the script folder is replaced on
# every update, so the skill sets SETLIST_ID_HOME (cache) and SETLIST_ID_OUT (tracklists) instead.
DATA = Path(os.path.expanduser(os.environ.get("SETLIST_ID_HOME", str(ROOT))))
CACHE = DATA / "cache"
OUT = Path(os.path.expanduser(os.environ.get("SETLIST_ID_OUT", str(DATA / "sets"))))

EXACT_ORDER = ["Spotify", "Apple Music", "Deezer"]
SEARCH_LINKS = [  # filled with the urlencoded "artist title"; DJ stores always, the rest as fallbacks
    ("Spotify", "https://open.spotify.com/search/{q}"),
    ("YouTube Music", "https://music.youtube.com/search?q={q}"),
    ("YouTube", "https://www.youtube.com/results?search_query={q}"),
    ("SoundCloud", "https://soundcloud.com/search/sounds?q={q}"),
    ("Tidal", "https://listen.tidal.com/search?q={q}"),
    ("Beatport", "https://www.beatport.com/search?q={q}"),
    ("Traxsource", "https://www.traxsource.com/search?term={q}"),
    ("Bandcamp", "https://bandcamp.com/search?q={q}&item_type=t"),
]


def log(msg: str = "", end: str = "\n") -> None:
    print(msg, end=end, file=sys.stderr, flush=True)


PROGRESS_HOOK = None  # the desktop app sets this to fn(stage: str, fraction: float | None)


def progress(stage: str, fraction: float | None = None) -> None:
    if PROGRESS_HOOK:
        PROGRESS_HOOK(stage, fraction)


def ffmpeg_exe() -> str:
    if exe := shutil.which("ffmpeg"):
        return exe
    import imageio_ffmpeg  # bundled binary, so friends don't need to install ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def js_runtime() -> dict:
    """yt-dlp needs a JavaScript runtime for YouTube; prefer the one shipped as a pip package."""
    try:
        import deno
        return {"deno": {"path": deno.find_deno_bin()}}
    except Exception:
        return {"node": {}} if shutil.which("node") else {}


def fmt_time(seconds: float) -> str:
    s = int(max(0, seconds))
    h, m, s = s // 3600, s // 60 % 60, s % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def parse_time(text: str) -> float:
    secs = 0.0
    for part in text.split(":"):
        secs = secs * 60 + float(part)
    return secs


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()[:80] or "set"


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def base_title(title: str) -> str:
    """Title without any (...) / [...] version tags."""
    return norm(re.sub(r"[\(\[].*?[\)\]]", "", title or ""))


# --------------------------------------------------------------------------- 1. audio

def fetch_audio(source: str) -> tuple[dict, Path]:
    """Return (info, path to 16 kHz mono wav). Results are cached per source id."""
    local = Path(source).expanduser()
    if local.exists():
        info = {"id": slugify(local.stem), "title": local.stem, "webpage_url": str(local.resolve()),
                "uploader": "", "description": "", "chapters": []}
        workdir = CACHE / info["id"]
        workdir.mkdir(parents=True, exist_ok=True)
        src_file = local
    else:
        def on_download(d):
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            if d.get("status") == "downloading" and total:
                progress("Downloading the set", d.get("downloaded_bytes", 0) / total)

        opts = {"quiet": True, "no_warnings": True, "noprogress": True, "noplaylist": True,
                "format": "bestaudio/best", "js_runtimes": js_runtime(), "progress_hooks": [on_download]}
        progress("Looking up the link")
        with yt_dlp.YoutubeDL(opts) as ydl:
            log(f"Fetching info for {source} ...")
            meta = ydl.extract_info(source, download=False)
        info = {k: meta.get(k) for k in ("id", "title", "uploader", "webpage_url", "description",
                                         "duration", "chapters", "thumbnail", "extractor_key")}
        info["id"] = slugify(f"{info.get('extractor_key') or ''}-{info['id']}")
        workdir = CACHE / info["id"]
        workdir.mkdir(parents=True, exist_ok=True)
        src_file = None
        if not (workdir / "audio.wav").exists():
            log(f"Downloading audio: {info['title']}")
            opts["outtmpl"] = str(workdir / "source.%(ext)s")
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([source])
            src_file = next(p for p in workdir.glob("source.*") if p.suffix not in (".part", ".wav"))

    (workdir / "info.json").write_text(json.dumps(info, indent=2, ensure_ascii=False))
    wav = workdir / "audio.wav"
    if not wav.exists():
        log("Converting to wav ...")
        progress("Preparing the audio")
        subprocess.run([ffmpeg_exe(), "-y", "-v", "error", "-i", str(src_file), "-ac", "1", "-ar", "16000",
                        "-sample_fmt", "s16", str(wav)], check=True)
        if src_file.parent == workdir:
            src_file.unlink()
    return info, wav


def read_clip(wav_path: Path, start: float, length: float) -> bytes:
    with wave.open(str(wav_path)) as w:
        rate = w.getframerate()
        w.setpos(min(int(start * rate), w.getnframes()))
        frames = w.readframes(int(length * rate))
        params = w.getparams()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as out:
        out.setparams(params)
        out.writeframes(frames)
    return buf.getvalue()


def wav_duration(wav_path: Path) -> float:
    with wave.open(str(wav_path)) as w:
        return w.getnframes() / w.getframerate()


# --------------------------------------------------------------------------- 2. recognition

def parse_match(out: dict) -> dict | None:
    track = out.get("track")
    if not out.get("matches") or not track:
        return None
    meta = {m.get("title"): m.get("text") for s in track.get("sections", []) for m in s.get("metadata", []) or []}
    hub = json.dumps(track.get("hub", {}))
    apple_id = None
    for action in track.get("hub", {}).get("actions", []) or []:
        if action.get("type") == "applemusicplay" and action.get("id"):
            apple_id = action["id"]
    apple = re.search(r'"(https://music\.apple\.com/[a-z]{2}/album/[^/"?]+/\d+)\?i=(\d+)', hub)
    apple_url = f"{apple.group(1)}?i={apple.group(2)}" if apple else None
    apple_id = apple_id or (apple.group(2) if apple else None)
    return {
        "shazam_key": track.get("key"),
        "title": track.get("title", ""),
        "artist": track.get("subtitle", ""),
        "album": meta.get("Album"),
        "label": meta.get("Label"),
        "released": meta.get("Released"),
        "genre": (track.get("genres") or {}).get("primary"),
        "isrc": track.get("isrc"),
        "cover": (track.get("images") or {}).get("coverart"),
        "shazam_url": track.get("url"),
        "apple_url": apple_url,
        "apple_id": apple_id,
        "offset": out["matches"][0].get("offset"),
    }


def track_key(answer: dict | None) -> str | None:
    """Identity of a sample's match, ignoring version tags so an original/extended flip isn't a 'change'."""
    m = parse_match(answer) if answer else None
    return f"{norm(m['artist'])}|{base_title(m['title'])}" if m else None


async def walk(grid: list[float], sample, jump: int, confirm: int = 3) -> None:
    """Decide which grid points to sample. `sample(t)` returns that point's track key.

    Once `confirm` samples in a row agree - the same track, or nothing recognised - we hop
    `jump` grid points at a time. Layered blends (samples alternating between two tracks) never
    reach that, so they stay fully sampled. If a hop lands on something different, the change happened inside the hop, so the
    skipped points are filled in - that finds the mix point and any short track in between.
    """
    keys: dict[int, str | None] = {}
    i, run, prev = 0, 0, None
    while i < len(grid):
        keys[i] = key = await sample(grid[i])
        if prev is not None and i - prev > 1 and key != keys[prev]:
            for j in range(prev + 1, i):
                keys[j] = await sample(grid[j])
            run = 0
            for j in range(i, -1, -1):  # count the agreeing samples ending at i
                if j not in keys or keys[j] != key:
                    break
                run += 1
        elif prev is not None and key == keys[prev]:
            run += 1
        else:
            run = 1
        prev = i
        nxt = i + (jump if run >= confirm else 1)
        i = min(nxt, len(grid) - 1) if i < len(grid) - 1 else nxt  # always check the very end


async def scan(wav: Path, workdir: Path, step: float, clip: float, start: float, end: float | None,
               interval: float, country: str, max_jump: float = 120) -> list[dict]:
    duration = wav_duration(wav)
    end = min(end or duration, duration)
    grid = []
    t = start
    while t + min(clip, 6) <= end:
        grid.append(round(t, 1))
        t += step

    # Answers are cached per point in time; earlier runs (adaptive or full) are reused as-is.
    cache_file = workdir / f"shazam_s{step:g}_c{clip:g}.json"
    cache: dict[str, dict | None] = json.loads(cache_file.read_text()) if cache_file.exists() else {}
    log(f"Set length {fmt_time(duration)} - up to {len(grid)} samples every {step:g}s"
        + (f", skipping ahead up to {max_jump:g}s inside confirmed tracks" if max_jump > step else ""))

    # Shazam's public endpoint rate-limits bursts with 429s (and shazamio retries those
    # forever), so fingerprint locally and send the requests ourselves, paced.
    shazam = Shazam(language="en-US", endpoint_country=country)
    stats = {"requests": 0, "ok": 0}
    async with httpx.AsyncClient(timeout=25, headers=shazam.headers()) as client:
        backoff, pace, streak = 30, interval, 0

        async def sample(t: float) -> str | None:
            nonlocal backoff, pace, streak
            if str(t) in cache:
                return track_key(cache[str(t)])
            stats["requests"] += 1
            where = (t - start) / max(1, end - start)
            sig = await shazam.core_recognizer.recognize_bytes(value=read_clip(wav, t, clip), options=None)
            body = Converter.data_search(sig.timezone, sig.signature.uri, sig.signature.samples, sig.timestamp)
            started = time.monotonic()
            for attempt in range(6):
                started = time.monotonic()
                url = ShazamUrl.SEARCH_FROM_FILE.format(language="en-US", device="iphone", endpoint_country=country,
                                                        uuid_1=str(uuid.uuid4()).upper(), uuid_2=str(uuid.uuid4()).upper())
                try:
                    r = await client.post(url, json=body)
                except httpx.HTTPError as e:
                    status = f"network error ({type(e).__name__})"
                else:
                    if r.status_code == 200:
                        out = r.json()  # keep the raw answer so parsing fixes don't need a rescan
                        cache[str(t)] = {"matches": out["matches"][:1], "track": out.get("track")} if out.get("matches") else None
                        stats["ok"] += 1
                        backoff, streak = 30, streak + 1
                        if streak >= 15:  # been fine for a while: speed back up
                            pace, streak = max(interval, pace * 0.85), 0
                        break
                    status = f"HTTP {r.status_code}"
                wait = backoff if status == "HTTP 429" else 5
                log(f"\r  {status} at {fmt_time(t)} - waiting {wait}s (attempt {attempt + 1}/6)      ", end="")
                progress(f"Shazam asked us to slow down – waiting {wait}s", where)
                await asyncio.sleep(wait)
                if status == "HTTP 429":  # rate-limited: slow down for the rest of the run
                    backoff, pace, streak = min(backoff * 2, 600), min(pace * 1.5, 20), 0
            else:
                log(f"\n  ! giving up on sample at {fmt_time(t)}")
            found = len({track_key(v) for v in cache.values() if v})
            log(f"\r  scanning {fmt_time(t)} / {fmt_time(end)}  ({stats['requests']} requests, "
                f"{found} tracks so far)          ", end="")
            progress(f"Listening for tracks – {found} found so far", where)
            if stats["requests"] % 10 == 0:
                cache_file.write_text(json.dumps(cache))
            await asyncio.sleep(max(0, pace - (time.monotonic() - started)))
            return track_key(cache.get(str(t)))

        await walk(grid, sample, max(1, int(max_jump // step)))
    cache_file.write_text(json.dumps(cache))
    if stats["requests"] and not stats["ok"]:
        sys.exit("\nEvery Shazam request failed - check your connection and re-run (progress is cached).")
    if stats["requests"]:
        log(f"\n  {stats['requests']} Shazam requests instead of {len(grid)}")
    hits = [(t, parse_match(cache[str(t)])) for t in grid if cache.get(str(t))]
    return [{**h, "t": t} for t, h in hits if h]


# --------------------------------------------------------------------------- 3. merge

def build_setlist(hits: list[dict], step: float, total: float) -> tuple[list[dict], list[dict], list[dict]]:
    groups: dict[str, dict] = {}
    for h in sorted(hits, key=lambda h: h["t"]):
        k = f"{norm(h['artist'])}|{norm(h['title'])}"
        g = groups.setdefault(k, {**h, "times": []})
        g["times"].append(h["t"])
    tracks = list(groups.values())
    for g in tracks:
        g["first"], g["last"], g["hits"] = min(g["times"]), max(g["times"]), len(g["times"])

    # Same artist + base title heard around the same time = one track matched as several
    # releases (original / extended / radio edit / remix). Majority vote picks the version.
    tracks.sort(key=lambda g: -g["hits"])
    merged: list[dict] = []
    for g in tracks:
        for m in merged:
            close = g["first"] <= m["last"] + 3 * step and g["last"] >= m["first"] - 3 * step
            if close and norm(g["artist"]) == norm(m["artist"]) and base_title(g["title"]) == base_title(m["title"]):
                m["times"] += g["times"]
                m["first"], m["last"] = min(m["first"], g["first"]), max(m["last"], g["last"])
                m["hits"] += g["hits"]
                m.setdefault("also_matched_as", []).append(f"{g['title']} ({g['hits']} hits)")
                break
        else:
            merged.append(g)

    # A track heard in only one sample is often a false match (crowd noise, MC, a layered loop),
    # so those go in a separate "possible" list. Ones inside another track's span are dropped.
    keep = sorted((g for g in merged if g["hits"] > 1), key=lambda g: g["first"])
    possible = sorted((g for g in merged if g["hits"] == 1 and not any(
        s["first"] < g["first"] < s["last"] for s in keep)), key=lambda g: g["first"])
    for g in possible:
        g["start"], g["confidence"] = g["first"], "possible"

    setlist, gaps = [], []
    prev_end = prev_start = 0.0
    for g in keep:
        if g["first"] - prev_end > 2.5 * step:
            gaps.append({"from": prev_end + (step if prev_end else 0), "to": g["first"]})
        # Shazam's offset says where in the track the clip came from -> estimate the mix-in point.
        est = g["first"] - (g.get("offset") or 0) if g["times"][0] == g["first"] else g["first"]
        # Shazam's offset hints where the clip sits in the track, but pitching and mash-ups make
        # it unreliable: only let it move the start back by up to one sample gap.
        g["start"] = max(prev_start, min(g["first"], max(est, g["first"] - step)))
        prev_start = g["start"]
        g["confidence"] = "high" if g["hits"] >= 3 else "medium"
        setlist.append(g)
        prev_end = max(prev_end, g["last"])
    if total - prev_end > 2.5 * step:
        gaps.append({"from": prev_end + step, "to": total})
    return setlist, gaps, possible


def parse_description(info: dict) -> list[dict]:
    """Tracklist lines from the description / chapters: '12:34 Artist - Title' or '3. Artist - Title'."""
    entries = []
    for ch in info.get("chapters") or []:
        if " - " in ch.get("title", ""):
            entries.append({"t": ch.get("start_time"), "text": ch["title"].strip()})
    if entries:
        return entries
    for line in (info.get("description") or "").splitlines():
        m = re.match(r"^\s*(?:\d{1,3}[.)]\s*)?[\[(]?(\d{1,2}:\d{2}(?::\d{2})?)?[\])]?\s*[-–|.]?\s*(.+?\s[-–]\s.+)$", line)
        if m and not re.search(r"https?://", m.group(2)):
            entries.append({"t": parse_time(m.group(1)) if m.group(1) else None, "text": m.group(2).strip()})
    return entries


def cross_reference(setlist: list[dict], gaps: list[dict], listed: list[dict]) -> list[dict]:
    """Mark tracks confirmed by the description; return listed tracks the audio scan missed."""
    used = set()
    for tr in setlist:
        label = norm(f"{tr['artist']} {tr['title']}")
        best = max(((difflib.SequenceMatcher(None, label, norm(e["text"])).ratio(), i) for i, e in enumerate(listed)),
                   default=(0, -1))
        if best[0] >= 0.6:
            tr["in_description"] = listed[best[1]]["text"]
            used.add(best[1])
    missed = [e for i, e in enumerate(listed) if i not in used]
    for gap in gaps:
        gap["listed"] = [e["text"] for e in missed if e["t"] is not None and gap["from"] - 60 <= e["t"] <= gap["to"]]
    return missed


# --------------------------------------------------------------------------- 4. links

class LinkResolver:
    """Exact links by ISRC - Deezer (free, no key) and Spotify (with SPOTIFY_CLIENT_ID /
    SPOTIFY_CLIENT_SECRET from developer.spotify.com). Everything else gets a search link."""

    def __init__(self, client: httpx.AsyncClient, cache_file: Path):
        self.client = client
        self.cache_file = cache_file
        self.cache = json.loads(cache_file.read_text()) if cache_file.exists() else {}
        self.spotify_creds = (os.environ.get("SPOTIFY_CLIENT_ID"), os.environ.get("SPOTIFY_CLIENT_SECRET"))
        self.spotify_token = None

    async def cached(self, key: str, fetch) -> str | None:
        if key not in self.cache:
            try:
                self.cache[key] = await fetch()
            except (httpx.HTTPError, ValueError, KeyError):
                return None  # don't cache failures
            self.cache_file.write_text(json.dumps(self.cache))
        return self.cache[key]

    async def deezer(self, isrc: str) -> str | None:
        async def fetch():
            data = (await self.client.get(f"https://api.deezer.com/2.0/track/isrc:{isrc}")).json()
            return data.get("link")
        return await self.cached(f"deezer:{isrc}", fetch)

    async def spotify(self, isrc: str) -> str | None:
        if not all(self.spotify_creds):
            return None

        async def fetch():
            if not self.spotify_token:
                r = await self.client.post("https://accounts.spotify.com/api/token", auth=self.spotify_creds,
                                           data={"grant_type": "client_credentials"})
                self.spotify_token = r.json()["access_token"]
            r = await self.client.get("https://api.spotify.com/v1/search", params={"q": f"isrc:{isrc}", "type": "track", "limit": 1},
                                      headers={"Authorization": f"Bearer {self.spotify_token}"})
            items = r.json()["tracks"]["items"]
            return items[0]["external_urls"]["spotify"] if items else ""
        return await self.cached(f"spotify:{isrc}", fetch) or None

    async def resolve(self, tr: dict) -> list[dict]:
        exact = {}
        if tr.get("apple_url"):
            exact["Apple Music"] = tr["apple_url"]
        if tr.get("isrc"):
            if url := await self.spotify(tr["isrc"]):
                exact["Spotify"] = url
            if url := await self.deezer(tr["isrc"]):
                exact["Deezer"] = url
        q = urllib.parse.quote(f"{tr['artist']} {tr['title']}")
        links = [{"label": label, "url": exact[label], "search": False} for label in EXACT_ORDER if label in exact]
        links += [{"label": label, "url": url.format(q=q), "search": True}
                  for label, url in SEARCH_LINKS if label not in exact]
        return links


async def add_links(tracks: list[dict]) -> None:
    async with httpx.AsyncClient(timeout=15) as client:
        resolver = LinkResolver(client, CACHE / "links.json")
        for i, tr in enumerate(tracks, 1):
            log(f"\r  streaming links {i}/{len(tracks)}", end="")
            progress("Finding streaming links", i / len(tracks))
            tr["links"] = await resolver.resolve(tr)
            # song.link's web page still resolves every platform from an Apple Music id.
            tr["songlink"] = f"https://song.link/i/{tr['apple_id']}" if tr.get("apple_id") else None
    log()


# --------------------------------------------------------------------------- 5. output

def write_outputs(info: dict, setlist: list[dict], gaps: list[dict], possible: list[dict],
                  missed: list[dict], outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    rows = sorted([{"kind": "track", "at": t["start"], **t} for t in setlist + possible] +
                  [{"kind": "gap", "at": g["from"], **g} for g in gaps], key=lambda r: (r["at"], r["kind"] == "gap"))

    def clean(ts):
        return [{k: v for k, v in t.items() if k not in ("times", "t", "offset")} for t in ts]
    (outdir / "tracklist.json").write_text(json.dumps(
        {"set": info, "tracks": clean(setlist), "possible": clean(possible), "unidentified": gaps,
         "listed_not_detected": missed}, indent=2, ensure_ascii=False))

    md = [f"# {info['title']}", "", f"<{info['webpage_url']}>", ""]
    n = 0
    for r in rows:
        if r["kind"] == "gap":
            hint = f" — description says: {'; '.join(r['listed'])}" if r.get("listed") else ""
            md.append(f"- `{fmt_time(r['from'])}` *ID – unidentified until {fmt_time(r['to'])}*{hint}")
            continue
        links = r.get("links") or []
        direct = [f"[{l['label']}]({l['url']})" for l in links if not l["search"]]
        search = [f"[{l['label']}]({l['url']})" for l in links if l["search"]]
        if r["confidence"] == "possible":
            md.append(f"- `{fmt_time(r['start'])}` *possible (heard once):* {r['artist']} – {r['title']}")
        else:
            n += 1
            md.append(f"{n}. `{fmt_time(r['start'])}` **{r['artist']} – {r['title']}**"
                      + (f" · {r['label']}" if r.get("label") else "") + f" ({r['confidence']})")
        if direct or r.get("songlink"):
            md.append(f"   - Stream: {' · '.join(direct)}" + (f" · [all platforms]({r['songlink']})" if r.get("songlink") else ""))
        if search:
            md.append(f"   - Search: {' · '.join(search)}")
    if missed:
        md += ["", "## In the description but not detected in the audio", ""] + [f"- {m['text']}" for m in missed]
    (outdir / "tracklist.md").write_text("\n".join(md) + "\n")

    (outdir / "tracklist.html").write_text(render_html(info, rows, missed))


def render_html(info: dict, rows: list[dict], missed: list[dict]) -> str:
    e = html.escape
    body, n = [], 0
    for r in rows:
        if r["kind"] == "gap":
            hint = f"<div class=hint>Description lists: {e('; '.join(r['listed']))}</div>" if r.get("listed") else ""
            body.append(f"<li class=gap><span class=time>{fmt_time(r['from'])}</span>"
                        f"<div><b>ID – unidentified</b> until {fmt_time(r['to'])}{hint}</div></li>")
            continue
        possible = r["confidence"] == "possible"
        if not possible:
            n += 1
        chips = "".join(f"<a class='chip{' search' if l['search'] else ''}' href='{e(l['url'])}' target=_blank "
                        f"rel=noopener>{'🔍 ' if l['search'] else ''}{e(l['label'])}</a>" for l in r.get("links") or [])
        if r.get("songlink"):
            chips += f"<a class='chip all' href='{e(r['songlink'])}' target=_blank rel=noopener>All platforms ↗</a>"
        meta = " · ".join(e(x) for x in (r.get("label"), r.get("released"), r.get("genre")) if x)
        conf = "possible · heard once" if possible else f"{r['confidence']} · {r['hits']} hits"
        alt = f"<div class=hint>Also matched as: {e(', '.join(r['also_matched_as']))}</div>" if r.get("also_matched_as") else ""
        desc = "<span class=ok title='Matches the tracklist in the description'>✓ in description</span>" if r.get("in_description") else ""
        cover = f"<img src='{e(r['cover'])}' alt='' loading=lazy>" if r.get("cover") else "<div class=noimg></div>"
        body.append(
            f"<li class='{'possible' if possible else ''}'><span class=time>{fmt_time(r['start'])}</span>{cover}<div class=info>"
            f"<div class=title>{'' if possible else f'{n}. '}{e(r['title'])}</div><div class=artist>{e(r['artist'])}</div>"
            f"<div class=meta>{meta} <span class='conf {r['confidence']}'>{conf}</span> {desc}</div>"
            f"{alt}<div class=chips>{chips}</div></div></li>")
    missed_html = ""
    if missed:
        missed_html = ("<h2>In the description but not detected in the audio</h2><ul class=missed>"
                       + "".join(f"<li>{e(m['text'])}</li>" for m in missed) + "</ul>")
    return f"""<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width, initial-scale=1">
<title>{e(info['title'])} – tracklist</title>
<style>
:root{{--bg:#fafaf9;--card:#fff;--fg:#1c1917;--mute:#78716c;--line:#e7e5e4;--accent:#ea580c;color-scheme:light}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0c0a09;--card:#1c1917;--fg:#f5f5f4;--mute:#a8a29e;--line:#292524;--accent:#fb923c;color-scheme:dark}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,-apple-system,sans-serif}}
main{{max-width:880px;margin:0 auto;padding:32px 16px}}
h1{{font-size:1.6rem;margin:0 0 4px}} h2{{font-size:1.1rem;margin-top:32px}}
.src{{color:var(--mute)}} .src a{{color:var(--accent)}}
ol{{list-style:none;padding:0;margin:24px 0 0}}
li{{display:flex;gap:14px;align-items:flex-start;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px;margin-bottom:10px}}
li.gap{{background:transparent;border-style:dashed;color:var(--mute)}}
li.possible{{opacity:.6;background:transparent}} li.possible:hover{{opacity:1}}
.time{{font:600 13px ui-monospace,monospace;color:var(--accent);min-width:56px;padding-top:2px}}
img,.noimg{{width:64px;height:64px;border-radius:8px;flex:none;object-fit:cover;background:var(--line)}}
.info{{min-width:0;flex:1}} .title{{font-weight:650}} .artist{{color:var(--mute)}}
.meta,.hint{{font-size:12.5px;color:var(--mute);margin-top:2px}}
.conf{{border-radius:99px;padding:1px 7px;font-weight:600}} .high{{background:#16a34a22;color:#16a34a}}
.medium{{background:#ca8a0422;color:#ca8a04}} .possible .conf{{background:var(--line);color:var(--mute)}} .ok{{color:#16a34a}}
.chips{{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}}
.chip{{font-size:12.5px;text-decoration:none;color:var(--fg);border:1px solid var(--line);border-radius:99px;padding:3px 10px}}
.chip:hover{{border-color:var(--accent)}} .chip.search{{color:var(--mute);border-style:dashed}} .chip.all{{color:var(--accent)}}
@media (max-width:520px){{li{{flex-wrap:wrap}} img,.noimg{{width:48px;height:48px}}}}
</style></head><body><main>
<h1>{e(info['title'])}</h1>
<div class=src>{e(info.get('uploader') or '')} · <a href="{e(info['webpage_url'])}">{e(info['webpage_url'])}</a> · {n} tracks identified</div>
<ol>{''.join(body)}</ol>{missed_html}
</main></body></html>"""


# --------------------------------------------------------------------------- main

async def run(source: str, step: float = 30, clip: float = 12, start: str = "0", end: str | None = None,
              interval: float = 3, country: str = "US", links: bool = True, out: Path | None = None,
              keep_audio: bool = False, max_jump: float = 120) -> tuple[Path, list[dict]]:
    """Full pipeline. Returns (output folder, tracklist)."""
    info, wav = fetch_audio(source)
    workdir = wav.parent
    hits = await scan(wav, workdir, step, clip, parse_time(start),
                      parse_time(end) if end else None, interval, country, max_jump)
    total = min(parse_time(end), wav_duration(wav)) if end else wav_duration(wav)
    if not keep_audio:
        wav.unlink()  # ~140 MB/hour; the Shazam answers stay cached
    setlist, gaps, possible = build_setlist(hits, step, total)
    missed = cross_reference(setlist, gaps, parse_description(info))
    if links and (setlist or possible):
        await add_links(setlist + possible)

    outdir = out or OUT / slugify(info["title"])
    write_outputs(info, setlist, gaps, possible, missed, outdir)
    log(f"\n{len(setlist)} tracks identified, {len(possible)} possible, {len(gaps)} unidentified stretches\n")
    return outdir, setlist


async def main() -> None:
    ap = argparse.ArgumentParser(description="Identify every track in a DJ set (SoundCloud / YouTube / local file).")
    ap.add_argument("source", help="SoundCloud or YouTube URL, or a path to an audio file")
    ap.add_argument("--step", type=float, default=30, help="seconds between samples (default 30; lower = finer, slower)")
    ap.add_argument("--clip", type=float, default=12, help="seconds of audio per sample (default 12)")
    ap.add_argument("--start", default="0", help="start scanning at mm:ss / h:mm:ss")
    ap.add_argument("--end", default=None, help="stop scanning at mm:ss / h:mm:ss")
    ap.add_argument("--interval", type=float, default=3, help="min seconds between Shazam requests (default 3)")
    ap.add_argument("--country", default="US", help="Shazam region, affects Apple Music links (default US)")
    ap.add_argument("--no-links", action="store_true", help="skip streaming-link lookup")
    ap.add_argument("--out", type=Path, default=None, help="output folder (default ./sets/<set-name>)")
    ap.add_argument("--max-jump", type=float, default=120,
                    help="inside a confirmed track, skip ahead up to this many seconds (default 120)")
    ap.add_argument("--thorough", action="store_true", help="sample every --step seconds, no skipping (slower)")
    ap.add_argument("--keep-audio", action="store_true", help="keep the downloaded audio (for re-scanning)")
    ap.add_argument("--open", action="store_true", help="open the HTML report when done")
    args = ap.parse_args()

    outdir, setlist = await run(args.source, args.step, args.clip, args.start, args.end, args.interval,
                                args.country, not args.no_links, args.out, args.keep_audio,
                                args.step if args.thorough else args.max_jump)
    for i, t in enumerate(setlist, 1):
        print(f"{i:>3}. {fmt_time(t['start']):>8}  {t['artist']} – {t['title']}  [{t['confidence']}]")
    log(f"\nReport: {outdir / 'tracklist.html'}")
    if args.open:
        webbrowser.open((outdir / "tracklist.html").resolve().as_uri())


if __name__ == "__main__":
    asyncio.run(main())
