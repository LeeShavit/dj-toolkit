"""Verify audio against the backup, then write the rekordbox import XML."""
import collections, datetime, glob, json, os, subprocess, urllib.parse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from mutagen import File as MF
from mutagen.flac import FLAC

S = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser("~")
ROOT = HOME + "/Music"
BK = HOME + "/Documents/music_files_backup_20261102_193419"
plan = json.load(open(f"{S}/plan.json"))
T = json.load(open(f"{S}/table.json"))

def sig(p):
    if p.lower().endswith(".flac"):
        return FLAC(p).info.md5_signature
    return subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-map", "0:a", "-f", "md5", "-"],
                          capture_output=True, text=True).stdout

def check(p):
    if p["state"] in ("merged", "quarantine"):
        return None
    d, b = os.path.join(ROOT, p["dest"]), os.path.join(BK, p["src"])
    if not os.path.exists(d):
        return "missing " + p["dest"]
    if sig(d) != sig(b):
        return "audio differs " + p["dest"]
    a = MF(d)
    g = (a.tags or {}).get("genre") if d.lower().endswith(".flac") else (a.tags.get("TCON") if a.tags else None)
    if p["state"] != "quarantine":
        got = g[0] if d.lower().endswith(".flac") and g else (g.text[0] if g else None)
        if got != p["genre"]:
            return f"genre {got} {p['dest']}"
    return None

with ThreadPoolExecutor(6) as ex:
    bad = [r for r in ex.map(check, plan) if r]
print("verified", len(plan), "problems", len(bad), bad[:10])

# remove source folders that are now empty
removed = []
for d in sorted({p["src"].split("/")[0] for p in plan}):
    full = os.path.join(ROOT, d)
    left = [f for f in os.listdir(full) if f not in (".DS_Store",)] if os.path.isdir(full) else None
    if left == []:
        ds = os.path.join(full, ".DS_Store")
        if os.path.exists(ds):
            os.remove(ds)
        os.rmdir(full)
        removed.append(d[:40])
    elif left:
        print("kept folder", d[:40], left[:5])
print("removed empty", removed)

# ---- XML
tree = ET.parse(f"{HOME}/Documents/rekordbox.xml")
root = tree.getroot()
col = root.find("COLLECTION")
pl = {p["src"]: p for p in plan}
def url(path):
    return "file://localhost" + urllib.parse.quote(path, safe="/,()&'!+=-_.~@:")
def src_of(t):
    p = urllib.parse.unquote(t.get("Location", "").replace("file://localhost", ""))
    return os.path.relpath(p, ROOT) if p.startswith(ROOT + "/") else None

ids = {}
merged = {}
maxid = 0
for t in col.findall("TRACK"):
    maxid = max(maxid, int(t.get("TrackID")))
    s = src_of(t)
    if s in pl and pl[s]["state"] == "merged":
        col.remove(t)
        merged[t.get("TrackID")] = pl[s]["merged_into"]
    elif s in pl:
        p = pl[s]
        t.set("Location", url(os.path.join(ROOT, p["dest"])))
        t.set("Genre", p["genre"])
        for a, k in (("Remixer", "remixer"), ("Label", "label")):
            if p["new"].get(k):
                t.set(a, p["new"][k])
        if p["camelot"]:
            t.set("Tonality", p["key"])
        ids[s] = t.get("TrackID")
today = datetime.date.today().isoformat()
KIND = {".flac": "FLAC File", ".mp3": "MP3 File", ".wav": "WAV File"}
tinfo = {x["path"]: x for x in T}
for p in plan:
    if p["state"] in ("quarantine", "merged") or p["src"] in ids:
        continue
    maxid += 1
    x = tinfo[p["src"]]
    full = os.path.join(ROOT, p["dest"])
    e = ET.SubElement(col, "TRACK")
    a = dict(TrackID=str(maxid), Name=p["title"] or "", Artist=p["artist"] or "", Composer="",
             Album=p["new"].get("album") or x.get("tags", {}).get("album", ""), Grouping="", Genre=p["genre"],
             Kind=KIND[x["ext"]], Size=str(os.path.getsize(full)), TotalTime=str(int(x.get("length") or 0)),
             DiscNumber="0", TrackNumber="0", Year=p["year"] or "0", AverageBpm=f"{float(p['bpm'] or 0):.2f}",
             DateAdded=today, BitRate=str((x.get("bitrate") or 0) // 1000), SampleRate=str(x.get("sr") or 44100),
             Comments=(p["new"]["comment"] if "comment" in p["new"] else x.get("tags", {}).get("comment", "")),
             PlayCount="0", Rating="0", Location=url(full), Remixer=p["new"].get("remixer", ""),
             Tonality=p["key"] or "", Label=p["new"].get("label") or x.get("tags", {}).get("label", ""), Mix="")
    e.attrib.update({k: str(v) for k, v in a.items()})
    ids[p["src"]] = str(maxid)
col.set("Entries", str(len(col.findall("TRACK"))))

rootnode = root.find("PLAYLISTS").find("NODE")
for x in rootnode.iter("TRACK"):
    if x.get("Key") in merged:
        x.set("Key", ids[merged[x.get("Key")]])
folder = ET.SubElement(rootnode, "NODE", Type="0", Name="Genres", Count="0")
order = ["Tech House", "Latin & Afro House", "Melodic & Deep House", "Dance Pop & Remixes", "Big Room & Festival",
         "Hard Dance & Hard Techno", "Classic House", "EDM Classics 2005-2015", "Classic Trance & Eurodance",
         "Breaks, Indie & Other"]
keep = [p for p in plan if p["state"] not in ("quarantine", "merged")]
counts = {}
for g in order:
    ms = sorted([p for p in keep if p["genre"] == g or g in p["also"]], key=lambda p: (p["artist"] or "").lower())
    n = ET.SubElement(folder, "NODE", Type="1", Name=g, KeyType="0", Entries=str(len(ms)))
    for p in ms:
        ET.SubElement(n, "TRACK", Key=ids[p["src"]])
    counts[g] = len(ms)
folder.set("Count", str(len(order)))
sets = ET.SubElement(rootnode, "NODE", Type="0", Name="Sets", Count="2")
for pre, name in (("Gaze Radio", "Gaze Radio - Goni Gonen"), ("GENDER BLENDER", "Gender Blender - NOYA")):
    ms = [p for p in keep if p["src"].startswith(pre)]
    n = ET.SubElement(sets, "NODE", Type="1", Name=name, KeyType="0", Entries=str(len(ms)))
    for p in ms:
        ET.SubElement(n, "TRACK", Key=ids[p["src"]])
rootnode.set("Count", str(len(rootnode.findall("NODE"))))
out = f"{HOME}/Documents/rekordbox_organized.xml"
tree.write(out, encoding="UTF-8", xml_declaration=True)

# re-read and validate
r2 = ET.parse(out).getroot()
c2 = r2.find("COLLECTION").findall("TRACK")
tk = {t.get("TrackID") for t in c2}
miss = [t.get("Location") for t in c2 if not os.path.exists(urllib.parse.unquote(t.get("Location").replace("file://localhost", "")))]
dangling = [x.get("Key") for x in r2.find("PLAYLISTS").iter("TRACK") if x.get("Key") not in tk]
print("xml tracks", len(c2), "unique ids", len(tk), "locations missing", len(miss), "dangling", len(dangling))
print(" missing:", [urllib.parse.unquote(m)[-50:] for m in miss])
print("playlists", counts)
print("in rb moved:", sum(p["incoll"] and p["dest"] != p["src"] for p in plan))
print("audio on disk in library", sum(1 for dp, dn, fn in os.walk(ROOT + "/DJ Library") for f in fn if f.lower().endswith((".flac", ".mp3", ".wav"))))
