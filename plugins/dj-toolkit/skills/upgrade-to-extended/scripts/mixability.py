#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["numpy", "imageio-ffmpeg>=0.5"]
# ///
"""Pick the best version of each song for DJ mixing - not necessarily the longest.

Scores every file on what matters when mixing:
  - beat strength in the first and last 16 s (a clean kick to mix in/out on)        3 + 3
  - length (more room to blend; capped at 6:00)                                      2.5
  - real audio quality (lossless with full spectrum > 320 MP3 > upscaled/low)        0.8
  - penalties: fade-out (-1.5) / fade-in (-1.0) on weak-beat edges, "(Mixed)" DJ-mix
    cuts (-3, they start/end mid-blend), > 2 s of leading silence (-0.3)

usage:
  uv run mixability.py score FILE [FILE ...]                 score files, print a table
  uv run mixability.py pick DIR [DIR ...] --out plan.csv     group versions of the same song
                                                              across folders, mark the winner
Read-only: never moves or deletes anything. Different remixes are different songs and are
never grouped together (the remixer's name is part of the song key).
"""
import argparse, csv, json, os, re, shutil, subprocess, sys, unicodedata
from concurrent.futures import ThreadPoolExecutor
import numpy as np

AUD = re.compile(r'\.(flac|mp3|wav|aiff?|m4a)$', re.I)
SR = 22050
FF = shutil.which('ffmpeg') or __import__('imageio_ffmpeg').get_ffmpeg_exe()


def norm(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower().replace('&', ' and ')
    return re.sub(r'[^a-z0-9]+', ' ', s).strip()


def probe(path):
    """duration (s), codec name, bitrate (kbps) from ffmpeg's banner (works without ffprobe)."""
    err = subprocess.run([FF, '-hide_banner', '-i', path], capture_output=True, text=True).stderr
    m = re.search(r'Duration: (\d+):(\d+):([\d.]+)', err)
    dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0
    c = re.search(r'Audio: (\w+)', err)
    b = re.search(r'bitrate: (\d+) kb/s', err)
    return dur, (c.group(1) if c else ''), (int(b.group(1)) if b else 0)


def decode(path, args):
    r = subprocess.run([FF, '-v', 'quiet', *args, '-i', path, '-ac', '1', '-ar', str(SR), '-f', 's16le', '-'],
                       capture_output=True)
    return np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768

def rms_env(x, hop):
    n = len(x) // hop
    return np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(1) + 1e-12)

def beat_strength(x):
    """Regularity of the low-frequency (kick) pulse, 0..1, over the given audio."""
    if len(x) < SR * 8: return 0.0
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR)
    X[(f < 35) | (f > 150)] = 0
    low = np.fft.irfft(X, len(x))
    env = rms_env(low, SR // 100)                      # 100 frames/s
    on = np.maximum(np.diff(env), 0)
    if on.sum() < 1e-6: return 0.0
    on = on - on.mean()
    ac = np.correlate(on, on, 'full')[len(on) - 1:]
    if ac[0] <= 0: return 0.0
    ac = ac / ac[0]
    lag = ac[40:76]                                     # 0.40-0.75 s  = 80-150 BPM
    return float(max(0.0, lag.max()))

def trim_silence(x, thr=0.003):
    e = rms_env(x, SR // 20)
    idx = np.where(e > thr)[0]
    if not len(idx): return x, 0.0, 0.0
    a, b = idx[0], idx[-1] + 1
    return x[a * SR // 20: b * SR // 20], a / 20, (len(e) - b) / 20

def fade_score(seg, at_start):
    """1.0 = clear fade (gradual level ramp), 0 = full level immediately."""
    e = rms_env(seg, SR // 4)                           # 4 frames/s
    if len(e) < 40: return 0.0
    body = np.median(e[len(e) // 3:]) if at_start else np.median(e[:len(e) * 2 // 3])
    edge = e[:12] if at_start else e[-12:][::-1]        # 3 s nearest the edge, ordered from edge inward
    if body <= 0: return 0.0
    first = edge[:4].mean() / body                      # first/last 1 s relative to body
    rising = np.mean(np.diff(edge) > 0)                 # steadily growing away from the edge
    return float(np.clip((0.5 - first) * 2, 0, 1) * (0.5 + 0.5 * rising))

def spectral_cutoff(path, dur):
    r = subprocess.run([FF, '-v', 'quiet', '-ss', str(max(0, dur / 2 - 5)), '-t', '10', '-i', path, '-ac', '1',
                        '-ar', '44100', '-f', 's16le', '-'], capture_output=True)
    x = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32)
    if len(x) < 44100: return 0
    frames = x[:len(x) // 4096 * 4096].reshape(-1, 4096) * np.hanning(4096)
    p = (np.abs(np.fft.rfft(frames, axis=1)) ** 2).mean(0)
    db = 10 * np.log10(p + 1e-9); f = np.fft.rfftfreq(4096, 1 / 44100)
    ref = np.median(db[(f > 1000) & (f < 4000)])
    above = np.where(db > ref - 50)[0]
    return int(f[above[-1]]) if len(above) else 0

def analyse(path):
    try:
        dur, codec, br = probe(path)
        head = decode(path, ['-t', '50'])
        tail = decode(path, ['-sseof', '-50'])
        h, lead, _ = trim_silence(head); t, _, trail = trim_silence(tail)
        cut = spectral_cutoff(path, dur)
        return dict(path=path, dur=dur, codec=codec, br=br, cutoff=cut, lead=lead, trail=trail,
                    intro_beat=beat_strength(h[:SR * 32]), outro_beat=beat_strength(t[-SR * 32:]),
                    in16=beat_strength(h[:SR * 16]), out16=beat_strength(t[-SR * 16:]),
                    fade_in=fade_score(h, True), fade_out=fade_score(t, False))
    except Exception as e:
        return dict(path=path, error=str(e))

def score(a):
    lossless = a['codec'] in ('flac', 'pcm_s16le', 'pcm_s24le', 'alac', 'pcm_s16be', 'pcm_s24be')
    q = (1.0 if a['cutoff'] >= 19500 else 0.4) if lossless else (0.7 if a['br'] >= 256 and a['cutoff'] >= 18500 else 0.3)
    mixed = bool(re.search(r'\(mixed\)|\bmixed\b', os.path.basename(a['path']), re.I))
    s = (3 * a['in16'] + 3 * a['out16'] + 2.5 * min(a['dur'], 360) / 360 + 0.8 * q
         - 1.5 * (a['fade_out'] >= 0.8) - 1.0 * (a['fade_in'] >= 0.8) - 3 * mixed - 0.3 * (a['lead'] > 2))
    return round(s, 3), q



def song_key(path):
    """artist + core title + remixer, so versions of one mix group together but different remixes don't."""
    stem = os.path.splitext(os.path.basename(path))[0]
    stem = re.sub(r'^\d+[\s.\-_]+', '', stem)                      # track numbers
    artist, _, title = stem.partition(' - ')
    if not title:
        artist, title = '', stem
    main_artist = norm(re.split(r',|&| x | feat', artist)[0])
    core = norm(re.sub(r'\s*[\(\[].*$', '', re.split(r'\s+-\s+', title)[0]))
    mix = norm(' '.join(re.findall(r'[\(\[]([^\)\]]*)[\)\]]', title)) + ' ' + ' '.join(re.split(r'\s+-\s+', title)[1:]))
    generic = {'extended', 'mix', 'radio', 'edit', 'club', 'original', 'version', 'vocal', 'main', 'remastered',
               'remaster', 'feat', 'ft', 'with', 'the', 'and', 'short', 'long', 'full', 'length', 'dub', 'mixed'}
    remixer = ' '.join(sorted(w for w in mix.split() if w not in generic and not w.isdigit()
                              and w not in main_artist.split() and len(w) > 1)) if re.search(r'remix|rmx|rework|bootleg|flip|edit', mix) else ''
    return (main_artist, core, remixer)


def fmt(s): return f"{int(s)//60}:{int(s)%60:02d}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('mode', choices=['score', 'pick'])
    ap.add_argument('paths', nargs='+')
    ap.add_argument('--out', default='mix_plan.csv')
    ap.add_argument('--margin', type=float, default=0.15, help='a challenger must beat the first-listed folder by this much')
    a = ap.parse_args()
    files = []
    for p in a.paths:
        p = os.path.expanduser(p)
        if os.path.isdir(p):
            files += [os.path.join(r, n) for r, _, ns in os.walk(p) for n in sorted(ns) if AUD.search(n) and not n.startswith('._')]
        elif os.path.isfile(p):
            files.append(p)
    with ThreadPoolExecutor(max(2, (os.cpu_count() or 4) - 1)) as ex:   # threads: ffmpeg does the work
        feats = list(ex.map(analyse, files))
    for f in feats:
        if 'error' not in f:
            f['score'], f['q'] = score(f)
    line = lambda f: (f"{f['score']:6.2f}  {fmt(f['dur']):>5}  in{f['in16']:.2f} out{f['out16']:.2f}  "
                      f"fadeIn{f['fade_in']:.1f} fadeOut{f['fade_out']:.1f}  q{f['q']}  {os.path.basename(f['path'])}")
    if a.mode == 'score':
        for f in sorted(feats, key=lambda f: -f.get('score', -99)):
            print(line(f) if 'error' not in f else f"ERROR {f['path']}: {f['error']}")
        return
    first_dir = os.path.abspath(os.path.expanduser(a.paths[0])).rstrip(os.sep) + os.sep
    groups = {}
    for f in feats:
        if 'error' not in f:
            groups.setdefault(song_key(f['path']), []).append(f)
    rows, multi = [], 0
    for key, fs in groups.items():
        fs.sort(key=lambda f: -f['score'])
        win = fs[0]
        incumbent = next((f for f in fs if f['path'].startswith(first_dir)), None)
        if incumbent and win is not incumbent and win['score'] - incumbent['score'] < a.margin:
            win = incumbent                                            # keep what's there unless clearly better
        if len(fs) > 1:
            multi += 1
        for f in fs:
            rows.append(dict(song=' - '.join(k for k in key if k), action='KEEP' if f is win else 'other version',
                             score=f['score'], length=fmt(f['dur']), intro_beat=round(f['in16'], 2), outro_beat=round(f['out16'], 2),
                             fade_in=round(f['fade_in'], 1), fade_out=round(f['fade_out'], 1), quality=f['q'], path=f['path']))
    with open(a.out, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print(f"{len(files)} files, {len(groups)} songs, {multi} with more than one version -> {a.out}")
    for key, fs in groups.items():
        if len(fs) > 1:
            print(' / '.join(k for k in key if k))
            for f in fs:
                print(('  KEEP ' if any(r['path'] == f['path'] and r['action'] == 'KEEP' for r in rows) else '       ') + line(f))


if __name__ == '__main__':
    main()
