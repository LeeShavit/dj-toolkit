# /// script
# requires-python = ">=3.9,<3.13"
# dependencies = [
#   "essentia",
#   "numpy",
# ]
# ///
"""Estimate BPM and key locally for songs missing them. Read-only on audio; results go to audio.json."""
import json, multiprocessing as mp, os, sys
S = os.environ["WORK"]
ROOT = os.environ["MUSIC_ROOT"]
SKIP = tuple(os.path.relpath(os.path.expanduser(p), os.path.expanduser(os.environ.get("MUSIC_ROOT", "/"))).rstrip("/") + "/"
             if os.path.isabs(os.path.expanduser(p)) else p.strip("/") + "/"
             for p in os.environ.get("PROTECTED", "").split(os.pathsep) if p)  # same rule as scan.py (trailing-separator match)

def work(rel):
    import essentia
    essentia.log.infoActive = False
    essentia.log.warningActive = False
    import essentia.standard as es
    audio = es.MonoLoader(filename=os.path.join(ROOT, rel), sampleRate=44100)()
    bpm, _, conf, _, _ = es.RhythmExtractor2013(method="multifeature")(audio)
    key, scale, strength = es.KeyExtractor(profileType="edma")(audio)
    return rel, {"bpm": round(float(bpm), 2), "bpm_conf": round(float(conf), 2),
                 "key": key, "scale": scale, "key_strength": round(float(strength), 3)}

def safe(rel):
    try:
        return work(rel)
    except Exception as e:
        return rel, {"error": repr(e)[:200]}

if __name__ == "__main__":
    rows = json.load(open(f"{S}/scan.json"))
    out_p = f"{S}/audio.json"
    done = json.load(open(out_p)) if os.path.exists(out_p) else {}
    todo = [r["path"] for r in rows if not (SKIP and r["path"].startswith(SKIP))
            and r["path"] not in done
            and not ({"bpm", "key"} <= set(r.get("tags", {})))]
    print("todo", len(todo), flush=True)
    with mp.get_context("spawn").Pool(max(2, (os.cpu_count() or 4) - 2), maxtasksperchild=10) as p:
        for i, (rel, res) in enumerate(p.imap_unordered(safe, todo)):
            done[rel] = res
            if i % 10 == 0:
                json.dump(done, open(out_p, "w"), ensure_ascii=False)
                print(i, rel[:60], res, flush=True)
    json.dump(done, open(out_p, "w"), ensure_ascii=False)
    print("done", len(done))
