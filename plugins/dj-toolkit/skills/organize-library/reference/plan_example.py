"""Build plan.json (genre, destination, tag changes) and the HTML review page. Touches no music files."""
import collections, json, os, re, urllib.parse
import xml.etree.ElementTree as ET
S = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser("~")
ROOT = HOME + "/Music"
LIB = "DJ Library"
QUAR = "_Duplicates"
T = json.load(open(f"{S}/table.json"))

NAMES = {"TH": "Tech House", "LA": "Latin & Afro House", "MH": "Melodic & Deep House", "DP": "Dance Pop & Remixes",
         "CH": "Classic House", "CT": "Classic Trance & Eurodance", "EH": "EDM Classics 2005-2015",
         "BR": "Big Room & Festival", "HD": "Hard Dance & Hard Techno", "OT": "Breaks, Indie & Other"}

def ids(s):
    out = []
    for p in s.split():
        if "-" in p:
            a, b = p.split("-")
            out += range(int(a), int(b) + 1)
        else:
            out.append(int(p))
    return out

PRIMARY = {
    "CT": "66 67 69 71 74 77 78 81 82 85 124 130 133 144 147 155 160 161 165 170 177 181 187 190 192 195 206 207 209 211 "
          "217 224 232 237 238 242 250 258 259 263 264 269 287 289 301 305 311 313 318 324 331 343 345 60",
    "EH": "16-65 100 153 157 162 166 168 169 175 180 182 185 196 198 202 216 231 254 265 271 278 280 282 284 304 309 326 "
          "329 330 332 335 341 142 173 310 346 374 411",
    "LA": "91 101 105 109 111 117 126 127 386 390 398 400 406 408 412 424 426 431 432 434 435 443 451 454 457 460 466 "
          "490 497 530 562",
    "MH": "88 103 115 388 396 393 399 407 409 403 414 416 421 438 440 442 450 453 456 477 487 500 514 544 554 564 574 605",
    "DP": "16 18 20 21 24 29 31 39 44 53 58 83 87 89 92 94 96 97 98 99 102 104 108 110 113 116 118 119 123 129 363 394 "
          "397 415 417 418 420 427 430 437 441 445 446 448 476 482 493 498 510 511 513 521 522 526 532 537 546 550 "
          "560 561 565 569 570 576 581 590 593 597 599 602 608 610 467 487",
    "BR": "52 65 120 121 489 512 515 540 548 551 563 568 579 582 584 586 592 611 54",
    "HD": "354-362 364-370 372 373 380 385 353 461",
    "OT": "143 179 203 226 334 339 347 350 371 447",
}
PRIMARY = {g: ids(v) for g, v in PRIMARY.items()}
# EH range 16-65 is the default for the Guetta-era folder; specific genre lists win over it.
pri = {}
for i in PRIMARY["EH"]:
    pri[i] = "EH"
for g, v in PRIMARY.items():
    if g != "EH":
        for i in v:
            pri[i] = g
for i in [34, 49]:
    pri[i] = "CH"

SECONDARY = {
    "TH": "105 106 125 391 426 428 469 505 542 500 392 104 110 575 1 87 102 436 91 127 460",
    "LA": "106 125 428 469 505 542 91 396 409 562 103 421 456 436",
    "MH": "109 562 544 564 54",
    "DP": "100 168 374 411 5 8",
    "CH": "87 84 208 214 392 411 604",
    "EH": "166 185 34",
    "BR": "551 588 611 123",
}
sec = collections.defaultdict(list)
for g, v in SECONDARY.items():
    for i in ids(v):
        sec[i].append(g)

UNSURE = set(ids("0 2 371 375 376 377 379 382 383 384 386 393 405 409 424 433 435 438 443 450 453 454 462 464 471 "
                 "480 485 490 491 496 504-507 516 518 519 520 529 533 534 539 541 545 552 558 559 571 573 578 583 587 "
                 "596 607 91 404 423 422 473"))

def default(i, x):
    p = x["path"][0]
    if p == "O":
        return "CH"
    if x["path"].startswith("Love Is"):
        return "EH"
    return "TH"

CAM = {"Abm": "1A", "G#m": "1A", "B": "1B", "Ebm": "2A", "D#m": "2A", "F#": "2B", "Gb": "2B", "Bbm": "3A", "A#m": "3A",
       "Db": "3B", "C#": "3B", "Fm": "4A", "Ab": "4B", "G#": "4B", "Cm": "5A", "Eb": "5B", "D#": "5B", "Gm": "6A",
       "Bb": "6B", "A#": "6B", "Dm": "7A", "F": "7B", "Am": "8A", "C": "8B", "Em": "9A", "G": "9B", "Bm": "10A",
       "D": "10B", "F#m": "11A", "Gbm": "11A", "A": "11B", "Dbm": "12A", "C#m": "12A", "E": "12B"}
REV = {"1A": "Abm", "1B": "B", "2A": "Ebm", "2B": "F#", "3A": "Bbm", "3B": "Db", "4A": "Fm", "4B": "Ab", "5A": "Cm",
       "5B": "Eb", "6A": "Gm", "6B": "Bb", "7A": "Dm", "7B": "F", "8A": "Am", "8B": "C", "9A": "Em", "9B": "G",
       "10A": "Bm", "10B": "D", "11A": "F#m", "11B": "A", "12A": "Dbm", "12B": "E"}

def parse_remixer(title):
    pats = [r"[-(\[]\s*([^()\[\]-]+?)\s+(?:Radio |Extended |Club |Original )?(?:Remix|Rework|Edit Remix|Bootleg|Mashup)\b"]
    for p in pats:
        m = re.search(p, title, re.I)
        if m:
            s = m.group(1).strip(" -'’")
            s = re.sub(r"\b(2\d{3}|Radio|Extended|Club|Original)\b", "", s, flags=re.I).strip()
            s = re.sub(r"'s$|’s$", "", s).strip()
            if s and len(s) < 60 and not re.fullmatch(r"(the|vip|new|official|a)", s, re.I):
                return s
    return None

def clean_comment(c):
    c = c or ""
    if re.fullmatch(r"(\s*[0-9A-F]{8}){6,}\s*", c):
        return ""
    c = re.sub(r"\s*\|?\s*Downloaded with OfflineDJ - https://www\.OfflineDJ\.com\s*", "", c)
    return c.strip(" |")

def clean_label(s):
    s = re.sub(r"^[℗©\s]*(\(?[PC]\)\s*)?(\d{4}\s+)?", "", s or "").strip()
    return re.sub(r",?\s*(distributed by|under (exclusive|excl)).*$", "", s, flags=re.I).strip()

# rekordbox collection
xroot = ET.parse(f"{HOME}/Documents/rekordbox.xml").getroot()
incoll = set()
for t in xroot.find("COLLECTION").findall("TRACK"):
    p = urllib.parse.unquote(t.get("Location", "").replace("file://localhost", ""))
    if p.startswith(ROOT + "/"):
        incoll.add(os.path.relpath(p, ROOT))

SETS = ("Gaze Radio", "GENDER BLENDER")
by_group = collections.defaultdict(list)
for i, x in enumerate(T):
    if x.get("dupgroup"):
        by_group[x["dupgroup"]].append(i)

# inherit genre calls across duplicates: the listed (first) id decides
for g, m in by_group.items():
    head = next((i for i in m if i in pri), None)
    for i in m:
        if head is not None:
            pri[i] = pri[head]
        if m[0] in sec and i != m[0]:
            sec[i] = sec[m[0]]
        if m[0] in UNSURE:
            UNSURE.add(i)

action = {}
for g, m in by_group.items():
    set_copy = [i for i in m if T[i]["path"].startswith(SETS)]
    rb = [i for i in m if T[i]["path"] in incoll]
    keep = set(set_copy) | set(rb)
    if not keep:
        tagged = sorted(m, key=lambda i: (-len(T[i].get("tags", {})), T[i]["path"]))
        keep = {tagged[0]}
    for i in m:
        action[i] = "keep" if i in keep else "dup"

plan = []
used = collections.defaultdict(list)
for i, x in enumerate(T):
    t = x.get("tags", {})
    dz = x["dz"]
    good = x["conf"] in ("high", "medium")
    genre_code = pri.get(i) or default(i, x)
    name = os.path.basename(x["path"])
    a, tt = dz.get("query", ["", ""])

    new = {}
    new["genre"] = NAMES[genre_code]
    if not t.get("title"):
        new["title"] = tt
    if not t.get("artist") and a:
        new["artist"] = a
    if good:
        if not t.get("album") and dz.get("album"):
            new["album"] = dz["album"]
        if dz.get("release") and (not t.get("year") or len(t["year"]) == 4 and False):
            new["year"] = dz["release"]
        if dz.get("isrc"):
            new["isrc"] = dz["isrc"]
        if dz.get("label") and not clean_label(t.get("label")):
            new["label"] = dz["label"]
        if dz.get("upc"):
            new["barcode"] = dz["upc"]
    if t.get("label") and clean_label(t["label"]) != t["label"] and "label" not in new:
        new["label"] = clean_label(t["label"]) or t["label"]
    rmx = parse_remixer(t.get("title") or tt or name)
    if rmx:
        new["remixer"] = rmx
    bpm = t.get("bpm")
    src_bpm = "tag"
    if not bpm:
        if good and dz.get("bpm"):
            bpm, src_bpm = str(round(dz["bpm"])), "deezer"
        elif x["au"].get("bpm"):
            bpm, src_bpm = str(round(x["au"]["bpm"])), "estimate"
        if bpm:
            new["bpm"] = bpm
    key = t.get("key")
    src_key = "tag"
    if key and key in REV:
        key = REV[key]
        new["key"] = key
    if not key and x["au"].get("key"):
        k = x["au"]["key"] + ("m" if x["au"]["scale"] == "minor" else "")
        k = REV.get(CAM.get(k, ""), k)
        key, src_key = k, "estimate"
        new["key"] = key
    c0 = t.get("comment", "")
    c1 = clean_comment(c0)
    if c1 != c0:
        new["comment"] = c1
    addart = good and not x.get("art") and dz.get("cover")

    act = action.get(i, "keep")
    if act == "dup":
        dest = f"{QUAR}/{name}"
        state = "quarantine"
    elif x["path"].startswith(SETS):
        dest = x["path"]
        state = "stay"
    else:
        dest = f"{LIB}/{NAMES[genre_code].replace('&', 'and')}/{name}"
        state = "move"
    used[dest].append(i)
    plan.append({"i": i, "src": x["path"], "dest": dest, "state": state, "code": genre_code, "genre": NAMES[genre_code],
                 "also": [NAMES[g] for g in sec.get(i, []) if g != genre_code], "unsure": i in UNSURE,
                 "conf": x["conf"], "artist": t.get("artist") or a, "title": t.get("title") or tt or name,
                 "bpm": bpm, "bpm_src": src_bpm, "key": key, "key_src": src_key, "camelot": CAM.get(key or ""),
                 "year": (t.get("year") or new.get("year") or "")[:4], "new": new, "art": bool(addart),
                 "cover": dz.get("cover") if addart else None, "incoll": x["path"] in incoll,
                 "fake": "FAKE" in c0 or any(s in name for s in ("CORAÇAO - 20th", "Like A G6 (with Naeleck)")) and x["path"].startswith("My playlist #59")})

# resolve filename collisions: keep unique destination by leaving later ones in place
for dest, m in used.items():
    if len(m) > 1:
        for n, i in enumerate(m[1:], 2):
            p = plan[i]
            b, e = os.path.splitext(p["dest"])
            p["dest"] = f"{b} ({n}){e}"
            p["renamed"] = True
json.dump(plan, open(f"{S}/plan.json", "w"), ensure_ascii=False, indent=0)

c = collections.Counter(p["genre"] for p in plan if p["state"] != "quarantine")
print(c.most_common())
print("states", collections.Counter(p["state"] for p in plan))
print("unsure", sum(p["unsure"] for p in plan if p["state"] != "quarantine"))
print("collisions renamed", [p["dest"] for p in plan if p.get("renamed")])
print("dup groups w/ both rekordbox copies:", [[T[i]["path"][:60] for i in m] for m in by_group.values()
                                              if sum(T[i]["path"] in incoll for i in m) > 1])
print("art to add", sum(p["art"] for p in plan), "no-art", sum(1 for x in T if not x.get("art")))
print("remixers", sum("remixer" in p["new"] for p in plan))
print("year adds", sum("year" in p["new"] for p in plan), "isrc", sum("isrc" in p["new"] for p in plan))
print("bpm adds", collections.Counter(p["bpm_src"] for p in plan), "key", collections.Counter(p["key_src"] for p in plan))
print("no key/bpm:", sum(not p["key"] for p in plan), sum(not p["bpm"] for p in plan))
print("fake", [p["src"] for p in plan if p["fake"]])
print("remixer samples", [(p["new"]["remixer"], p["title"][:50]) for p in plan if "remixer" in p["new"]][::25])

# ---- review page
keep = [p for p in plan if p["state"] != "quarantine"]
data = {"genres": [], "dups": [{"src": p["src"], "artist": p["artist"], "title": p["title"]} for p in plan if p["state"] == "quarantine"]}
order = ["TH", "LA", "MH", "DP", "BR", "HD", "CH", "EH", "CT", "OT"]
for code in order:
    ts = sorted([p for p in keep if p["code"] == code], key=lambda p: (p["artist"] or "").lower())
    data["genres"].append({"name": NAMES[code], "tracks": [
        {"a": p["artist"], "t": p["title"], "b": p["bpm"], "be": p["bpm_src"] == "estimate", "k": p["camelot"] or p["key"],
         "ke": p["key_src"] == "estimate", "y": p["year"], "u": p["unsure"], "c": p["conf"], "s": p["state"] == "stay",
         "o": p["src"].split("/")[0][:28], "x": p["also"], "f": p["fake"]} for p in ts]})
tpl = open(f"{S}/review.tpl.html").read()
html = tpl.replace("__DATA__", json.dumps(data, ensure_ascii=True))
out = f"{HOME}/Documents/rekordbox_library_browser.html"
open(out, "w").write(html)
print("wrote", out)
