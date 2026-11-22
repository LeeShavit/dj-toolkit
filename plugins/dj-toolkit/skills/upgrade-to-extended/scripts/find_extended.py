#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["mutagen"]
# ///
"""Find the extended / club version of every track in a DJ library (Deezer search + iTunes fallback).
Read-only on the library. Writes matches.json, matches.csv and extended-list.txt (one
"Artist - Title (Mix)" line per track to download) to --out.

usage: uv run find_extended.py --library DIR [--library DIR ...] --out DIR [--limit N]

Rules (learned on a real 565-song library):
  - "already extended": >= 5:00, or labelled extended/club/12"/original mix and >= 4:00
  - candidate must be >= max(current + 45 s, 4:00), title similarity >= .85, artist must match
  - reject radio / instrumental / live / mixed / DJ-mix / megamix / sped-up / edit (unless extended or club)
  - a remix's extended version must be by the SAME remixer (>= 50% remixer-name overlap), never a different remix
  - status: already | found (high confidence) | review (plausible, check it) | none
"""
import argparse
import os, re, json, csv, time, subprocess, unicodedata, urllib.parse, urllib.request
from difflib import SequenceMatcher

ap = argparse.ArgumentParser()
ap.add_argument("--library", action="append", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--limit", type=int, default=0)
A = ap.parse_args()
LIBS = [os.path.abspath(os.path.expanduser(l)) for l in A.library]
OUT = os.path.abspath(os.path.expanduser(A.out)); os.makedirs(OUT, exist_ok=True)
EXTS = ('.mp3', '.flac', '.m4a', '.wav', '.aiff', '.aif')
CACHE_F = os.path.join(OUT, 'http_cache.json')
cache = json.load(open(CACHE_F)) if os.path.exists(CACHE_F) else {}

def get(url, pause):
    if url in cache: return cache[url]
    for attempt in range(4):
        try:
            d = json.loads(subprocess.run(['curl', '-s', '-m', '20', '-A', 'Mozilla/5.0', url],
                                          capture_output=True, text=True).stdout)
            if isinstance(d, dict) and d.get('error'):
                time.sleep(5 * (attempt + 1)); continue
            cache[url] = d; time.sleep(pause); return d
        except Exception:
            time.sleep(5 * (attempt + 1))
    return {}

def norm(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower()
    s = re.sub(r'[\(\[][^\)\]]*(feat|ft\.|with )[^\)\]]*[\)\]]', ' ', s)
    s = re.sub(r'\b(feat\.?|ft\.?)\s.*', ' ', s)
    s = s.replace('&', ' and ')
    return re.sub(r'[^a-z0-9]+', ' ', s).strip()

MIXWORDS = r'(remix|mix|edit|bootleg|rework|version|vip|dub|extended|radio|club|flip|re-?edit|instrumental)'
def split_title(t):
    t = t.strip()
    m = re.match(r'^(.*?)\s+-\s+(.+)$', t)
    if m and re.search(MIXWORDS, m.group(2), re.I): return m.group(1), m.group(2)
    m = re.match(r'^(.*?)\s*[\(\[]([^\(\)\[\]]*' + MIXWORDS + r'[^\(\)\[\]]*)[\)\]]\s*$', t, re.I)
    if m: return m.group(1), m.group(2)
    return t, ''

GENERIC = {'radio', 'edit', 'mix', 'remix', 'version', 'extended', 'club', 'original', 'single', 'the', 's',
           'short', 'long', 'vocal', 'main', 'full', 'length', 'album', 'remaster', 'remastered', 'and', 'x', 'vs', 'in', 'edition'}
def remixer_tokens(mix):
    toks = set(norm(mix).split()) - GENERIC
    toks -= {str(y) for y in range(1950, 2030)}
    return toks

def artists_of(a):
    return [norm(x) for x in re.split(r',|&| x | vs\.? | feat\.? | ft\.? | and ', a, flags=re.I) if norm(x)]

GOOD = [('extended', 4), ('club mix', 3), ('club version', 3), ('original mix', 3), ('12', 3), ('inch', 3),
        ('long version', 2), ('full length', 2), ('full version', 2), ('original version', 1), ('vocal mix', 1),
        ('main mix', 2), ('album version', 1), ('original club', 3)]
BAD = r'(radio|instrumental|acapella|a cappella|karaoke|live|mixed|dj mix|continuous|megamix|medley|sped up|slowed|nightcore|cover|tribute|originally performed|reprise|intro|short)'

def judge(c_title, c_ver, c_artist, c_album, c_dur, tr):
    base_c = norm(re.sub(r'\s*[\(\[].*$', '', c_title).split(' - ')[0])
    if SequenceMatcher(None, base_c, tr['nbase']).ratio() < 0.85 and not (tr['nbase'] and tr['nbase'] in base_c and len(base_c) - len(tr['nbase']) < 6):
        return None
    ca = norm(c_artist)
    if not any(a and (a in ca or ca in a) for a in tr['artists']) and not (tr['rmx'] and tr['rmx'] <= set(ca.split())):
        return None
    v = norm(c_ver or ' '.join(re.findall(r'[\(\[]([^\)\]]*)[\)\]]', c_title)) + ' ' + ' '.join(c_title.split(' - ')[1:]))
    alb = norm(c_album)
    if re.search(BAD, v) and 'extended' not in v: return None
    if re.search(r'\b(mixed|dj mix|continuous|megamix)\b', alb): return None
    if re.search(r'\bdub\b', v) and 'dub' not in norm(tr['mix']): return None
    if 'edit' in v.split() and 'extended' not in v and 'club' not in v: return None
    if c_dur < max(tr['dur'] + 45, 240): return None
    score, conf = 0.0, 'review'
    kw = max([w for k, w in GOOD if re.search(r'\b' + k + r'\b', v)] or [0])
    if tr['rmx']:
        cand = set(v.split()) - GENERIC
        ov = len(tr['rmx'] & (cand | set(ca.split()))) / len(tr['rmx'])
        if ov < 0.5: return None
        score += 6 * ov + kw
        if ov >= 0.99 and (kw or 'remix' in v or 'mix' in v): conf = 'high'
    else:
        mine = set(' '.join(tr['artists']).split())
        others = set(v.split()) - GENERIC - {'12', 'inch', 'dub', 'vocal'} - mine
        if re.search(r'\b(remix|rmx|bootleg|rework|flip)\b', v) and kw < 3: return None
        if others and kw < 3 and not re.search(r'\boriginal\b', v): return None
        if not v and c_dur < 300: return None
        score += kw + (0.5 if not v else 0) - (3 if others else 0)
        if kw >= 3 and not others: conf = 'high'
    score += min(c_dur, 480) / 480
    return score, conf, v

def deezer_search(q):
    d = get('https://api.deezer.com/search?limit=50&q=' + urllib.parse.quote(q), 0.13)
    return [dict(src='deezer', title=t['title'], ver=t.get('title_version', ''), artist=t['artist']['name'],
                 album=t['album']['title'], dur=t['duration'], link=t['link'], isrc=t.get('isrc', '')) for t in d.get('data', [])]

def itunes_search(q):
    d = get('https://itunes.apple.com/search?entity=song&limit=50&term=' + urllib.parse.quote(q), 3.2)
    return [dict(src='apple', title=t['trackName'], ver='', artist=t['artistName'], album=t.get('collectionName', ''),
                 dur=t.get('trackTimeMillis', 0) // 1000, link=t.get('trackViewUrl', ''), isrc='') for t in d.get('results', [])]

def probe(p):
    import mutagen
    m = mutagen.File(p, easy=True)
    if m is None: return 0.0, '', ''
    g = lambda k: (m.get(k) or [''])[0] if m.tags else ''
    return float(m.info.length or 0), g('artist'), g('title')

files = sorted(os.path.join(d, f) for LIB in LIBS for d, _, n in os.walk(LIB) for f in n
               if f.lower().endswith(EXTS) and not f.startswith('._') and '/Reports' not in d)
if A.limit: files = files[:A.limit]
def lib_of(p): return next(L for L in LIBS if p.startswith(L + os.sep))
results = []
for i, p in enumerate(files):
    dur, artist, title = probe(p)
    LIB = lib_of(p); rel = os.path.relpath(p, LIB)
    if not artist or not title:
        stem = os.path.splitext(os.path.basename(p))[0]
        artist, _, title = stem.partition(' - ')
    base, mix = split_title(title)
    tr = dict(path=p, file=rel, folder=rel.split('/')[0], artist=artist, title=title, base=base, mix=mix, dur=round(dur),
              nbase=norm(base), artists=artists_of(artist), rmx=remixer_tokens(mix) if not re.fullmatch(
                  r'\s*(radio( edit| mix| version)?|single( edit| version)?|edit|original( mix)?|short( edit)?)\s*', mix, re.I) else set())
    # the artist's own name in a mix title ("Jaxx Radio Mix" by Basement Jaxx) is not a remixer
    tr['rmx'] = tr['rmx'] - set((tr['artists'][:1] or [''])[0].split())
    nm = norm(mix)
    if dur >= 300 or (re.search(r'\b(extended|club mix|12|inch|original mix)\b', nm) and dur >= 240):
        tr['status'] = 'already'
    else:
        main = tr['artists'][0] if tr['artists'] else artist
        qs = [f'{main} {norm(base)}', f'{norm(base)} {" ".join(sorted(tr["rmx"]))}' if tr['rmx'] else f'{norm(base)} {main} extended']
        cands = []
        for q in qs: cands += deezer_search(q)
        best = []
        for c in cands:
            j = judge(c['title'], c['ver'], c['artist'], c['album'], c['dur'], tr)
            if j: best.append((j[0], j[1], c))
        if not any(b[1] == 'high' for b in best):
            for q in qs[:1] + ([f'{norm(base)} {" ".join(sorted(tr["rmx"]))}'] if tr['rmx'] else []):
                for c in itunes_search(q):
                    j = judge(c['title'], c['ver'], c['artist'], c['album'], c['dur'], tr)
                    if j: best.append((j[0], j[1], c))
        best.sort(key=lambda b: (b[1] == 'high', b[0]), reverse=True)
        seen, alts = set(), []
        for s, cf, c in best:
            k = (norm(c['title']), c['dur'] // 5)
            if k in seen: continue
            seen.add(k); alts.append(dict(c, conf=cf, score=round(s, 2)))
        tr['status'] = ('found' if alts[0]['conf'] == 'high' else 'review') if alts else 'none'
        tr['match'] = alts[0] if alts else None
        tr['alts'] = alts[1:4]
    tr['rmx'] = sorted(tr['rmx'])
    results.append(tr)
    if i % 25 == 0:
        json.dump(cache, open(CACHE_F, 'w')); print(i, len(files), flush=True)

json.dump(cache, open(CACHE_F, 'w'))
json.dump(results, open(os.path.join(OUT, 'matches.json'), 'w'), indent=1, ensure_ascii=False)
fmt = lambda s: f'{int(s) // 60}:{int(s) % 60:02d}'
with open(os.path.join(OUT, 'matches.csv'), 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['status', 'folder', 'artist', 'current title', 'current length', 'extended version', 'by', 'length', 'link', 'beatport search'])
    for r in results:
        m = r.get('match') or {}
        q = urllib.parse.quote(f"{r['artists'][0] if r['artists'] else r['artist']} {r['base']}")
        w.writerow([r['status'], r['folder'], r['artist'], r['title'], fmt(r['dur']), m.get('title', ''), m.get('artist', ''),
                    fmt(m['dur']) if m else '', m.get('link', ''), f'https://www.beatport.com/search?q={q}'])
from collections import Counter
print('DONE', Counter(r['status'] for r in results))

# downloader list: what to fetch next (found first, then review)
def mixname(m):
    t = m['title']; v = m.get('ver') or ''
    return t if (not v or v.lower() in t.lower()) else f"{t} ({v})"
for st, fn in (('found', 'extended-list.txt'), ('review', 'extended-review.txt')):
    with open(os.path.join(OUT, fn), 'w') as f:
        for r in results:
            if r['status'] == st and r.get('match'):
                f.write(f"{r['match']['artist']} - {mixname(r['match'])}\n")
    print('wrote', os.path.join(OUT, fn))
