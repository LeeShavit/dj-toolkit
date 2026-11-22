import collections, json, os, re, subprocess, urllib.parse
from concurrent.futures import ThreadPoolExecutor
from mutagen import File as MF
from mutagen.flac import FLAC
import xml.etree.ElementTree as ET
R=os.path.expanduser("~/Music")
files=[]
for top in ("DJ Library","_Duplicates","Music"):
    for dp,dn,fn in os.walk(f"{R}/{top}"):
        for f in fn:
            if f.lower().endswith((".flac",".mp3",".wav")): files.append(os.path.join(dp,f))
def pcm(p):
    # same decoded format for every file so a copy matches across containers
    return subprocess.run(["ffmpeg","-v","error","-i",p,"-map","0:a:0","-f","s16le","-ac","2","-ar","44100","-t","60","-"],capture_output=True).stdout
import hashlib
def sig(p):
    return hashlib.md5(pcm(p)).hexdigest()
with ThreadPoolExecutor(6) as ex: sigs=list(ex.map(sig,files))
g=collections.defaultdict(list)
for f,s in zip(files,sigs): g[s].append(os.path.relpath(f,R))
lib=[v for v in g.values() if sum(x.startswith("DJ Library") for x in v)>1]
print("files",len(files))
print("identical audio inside DJ Library:",lib)
d=[f for v in g.values() for f in v if f.startswith("_Duplicates")]
print("_Duplicates total",sum(x.startswith("_Duplicates") for x in map(lambda f:os.path.relpath(f,R),files)))
orph=[v for v in g.values() if all(not x.startswith("DJ Library") for x in v)]
print("groups with NO copy in DJ Library:",orph)
print("Apple Music copies with a DJ Library copy:",sum(1 for v in g.values() if any(x.startswith("Music/") for x in v) and any(x.startswith("DJ Library") for x in v)),"of",sum(x.startswith("Music/") for v in g.values() for x in v))
# near-duplicates: same artist+title words, within 2s
def key(p):
    n=os.path.splitext(os.path.basename(p))[0].lower()
    n=re.sub(r"\s\(\d\)$","",n)
    return re.sub(r"[^a-z0-9]+","",n)
rows=collections.defaultdict(list)
for dp,dn,fn in os.walk(f"{R}/DJ Library"):
    for f in fn:
        if f.lower().endswith((".flac",".mp3",".wav")):
            p=os.path.join(dp,f); i=MF(p).info
            base=re.sub(r"\s*-\s*(radio edit|radio mix|edit|original mix|single version)\s*$","",os.path.splitext(f)[0],flags=re.I)
            rows[key(base)].append((round(i.length),getattr(i,"bits_per_sample",0),getattr(i,"bitrate",0)//1000,os.path.relpath(p,R+"/DJ Library")))
print("--- same name, different audio")
for k,v in rows.items():
    if len(v)>1:
        print(k[:40]); [print("   ",x) for x in sorted(v)]
