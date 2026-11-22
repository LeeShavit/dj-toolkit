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
"""Setlist ID desktop app: a small web page served from this computer only (127.0.0.1).

Started by the "Setlist ID" launcher, which runs `uv run app.py`.
"""
from __future__ import annotations

import asyncio
import html
import json
import threading
import traceback
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import setlist_id as core

PORT = 8765
JOB = {"running": False, "stage": "", "fraction": None, "error": None, "result": None, "source": ""}
LOCK = threading.Lock()


def on_progress(stage: str, fraction: float | None) -> None:
    with LOCK:
        JOB["stage"], JOB["fraction"] = stage, fraction


core.PROGRESS_HOOK = on_progress


def friendly_error(exc: Exception) -> str:
    text = str(exc)
    if "Unsupported URL" in text or "is not a valid URL" in text:
        return "That doesn't look like a SoundCloud or YouTube link. Copy the link from the address bar and try again."
    if "Private" in text or "private" in text or "Sign in" in text or "404" in text:
        return "Couldn't open that set – it may be private, deleted, or region-locked."
    if "Every Shazam request failed" in text or "ConnectError" in text or "getaddrinfo" in text:
        return "Couldn't reach the internet (or Shazam). Check your connection and press Go again – progress is saved."
    return f"Something went wrong: {text[:300]}"


def run_job(source: str) -> None:
    try:
        outdir, _ = asyncio.run(core.run(source))
        with LOCK:
            JOB["result"] = f"/sets/{urllib.parse.quote(outdir.name)}/"
    except SystemExit as e:  # core exits when every Shazam request fails
        with LOCK:
            JOB["error"] = friendly_error(Exception(str(e)))
    except Exception as e:
        traceback.print_exc()
        with LOCK:
            JOB["error"] = friendly_error(e)
    finally:
        with LOCK:
            JOB["running"] = False


def past_sets() -> list[dict]:
    sets = []
    for f in core.OUT.glob("*/tracklist.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        sets.append({"slug": f.parent.name, "title": data["set"].get("title") or f.parent.name,
                     "tracks": len(data.get("tracks", [])), "mtime": f.stat().st_mtime})
    return sorted(sets, key=lambda s: -s["mtime"])


def home_page() -> str:
    e = html.escape
    rows = "".join(
        f"<li><a href='/sets/{urllib.parse.quote(s['slug'])}/'>{e(s['title'])}</a><span>{s['tracks']} tracks</span></li>"
        for s in past_sets()) or "<li class=empty>Nothing yet – your tracklists will show up here.</li>"
    return PAGE.replace("{{SETS}}", rows)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # keep the launcher window quiet
        pass

    def send(self, body: str | bytes, ctype: str = "text/html; charset=utf-8", status: int = 200) -> None:
        data = body.encode() if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urllib.parse.unquote(urllib.parse.urlparse(self.path).path)
        if path == "/":
            return self.send(home_page())
        if path == "/status":
            with LOCK:
                return self.send(json.dumps(JOB), "application/json")
        if path.startswith("/sets/"):
            slug = path.split("/")[2]
            report = (core.OUT / slug / "tracklist.html").resolve()
            if report.parent.parent == core.OUT.resolve() and report.exists():
                page = report.read_text(encoding="utf-8").replace(
                    "<main>", "<main><a class=back href='/' style='color:var(--accent);text-decoration:none'>← Setlist ID</a>", 1)
                return self.send(page)
        self.send("Not found", "text/plain", 404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        if self.path == "/start":
            source = (body.get("url") or "").strip()
            with LOCK:
                if JOB["running"]:
                    return self.send(json.dumps({"error": "Already working on a set – wait for it to finish."}), "application/json", 409)
                if not source:
                    return self.send(json.dumps({"error": "Paste a link first."}), "application/json", 400)
                JOB.update(running=True, stage="Starting…", fraction=None, error=None, result=None, source=source)
            threading.Thread(target=run_job, args=(source,), daemon=True).start()
            return self.send(json.dumps({"ok": True}), "application/json")
        if self.path == "/quit":
            self.send(json.dumps({"ok": True}), "application/json")
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        self.send("Not found", "text/plain", 404)


PAGE = """<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width, initial-scale=1">
<title>Setlist ID</title>
<style>
:root{--bg:#fafaf9;--card:#fff;--fg:#1c1917;--mute:#78716c;--line:#e7e5e4;--accent:#ea580c;--err:#dc2626;color-scheme:light}
@media (prefers-color-scheme:dark){:root{--bg:#0c0a09;--card:#1c1917;--fg:#f5f5f4;--mute:#a8a29e;--line:#292524;--accent:#fb923c;--err:#f87171;color-scheme:dark}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:640px;margin:0 auto;padding:56px 16px}
h1{font-size:2rem;margin:0}
.lead{color:var(--mute);margin:4px 0 28px}
form{display:flex;gap:8px;flex-wrap:wrap}
input{flex:1 1 280px;font:inherit;padding:14px 16px;border:1px solid var(--line);border-radius:12px;background:var(--card);color:var(--fg)}
input:focus{outline:2px solid var(--accent);outline-offset:-1px}
button{font:inherit;font-weight:650;padding:14px 26px;border:0;border-radius:12px;background:var(--accent);color:#fff;cursor:pointer}
button:disabled{opacity:.5;cursor:default}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px;margin-top:20px}
.bar{height:8px;background:var(--line);border-radius:99px;overflow:hidden;margin-top:12px}
.bar i{display:block;height:100%;width:0;background:var(--accent);transition:width .4s}
.bar.indeterminate i{width:30%;animation:slide 1.2s infinite ease-in-out}
@keyframes slide{from{margin-left:-30%}to{margin-left:100%}}
.note{color:var(--mute);font-size:14px;margin-top:10px}
.err{color:var(--err)}
h2{font-size:1rem;margin:44px 0 8px;color:var(--mute);font-weight:600}
ul{list-style:none;padding:0;margin:0}
ul li{display:flex;justify-content:space-between;gap:12px;padding:12px 0;border-bottom:1px solid var(--line)}
ul li a{color:var(--fg);text-decoration:none;font-weight:550;min-width:0;overflow-wrap:anywhere} ul li a:hover{color:var(--accent)}
ul li span{color:var(--mute);font-size:14px;white-space:nowrap}
ul li.empty{color:var(--mute)}
.quit{background:none;color:var(--mute);padding:0;font-weight:400;font-size:14px;margin-top:40px;text-decoration:underline}
</style></head><body><main>
<h1>Setlist ID</h1>
<p class=lead>Paste a SoundCloud or YouTube link to a DJ set and get every track, with links to stream it.</p>
<form id=f><input id=url placeholder="https://soundcloud.com/…" autocomplete=off autofocus><button id=go>Go</button></form>
<div class=card id=job hidden>
  <div id=stage>Starting…</div>
  <div class=bar id=bar><i id=fill></i></div>
  <div class=note id=note>A one-hour set takes about 15–20 minutes. You can leave this page open and do something else.</div>
</div>
<h2>Your tracklists</h2>
<ul>{{SETS}}</ul>
<button class=quit id=quit>Quit Setlist ID</button>
</main>
<script>
const $ = id => document.getElementById(id);
async function poll(){
  const s = await (await fetch('/status')).json();
  if (!s.running && !s.error && !s.result) return;
  $('job').hidden = false;
  if (s.result){ location.href = s.result; return; }
  if (s.error){
    $('stage').innerHTML = ''; $('stage').append(Object.assign(document.createElement('span'), {className:'err', textContent:s.error}));
    $('bar').hidden = true; $('note').hidden = true; $('go').disabled = false; return;
  }
  $('go').disabled = true; $('bar').hidden = false; $('note').hidden = false;
  $('stage').textContent = s.stage || 'Working…';
  $('bar').classList.toggle('indeterminate', s.fraction == null);
  $('fill').style.width = s.fraction == null ? '' : (s.fraction * 100).toFixed(1) + '%';
  setTimeout(poll, 1000);
}
$('f').onsubmit = async ev => {
  ev.preventDefault();
  const r = await fetch('/start', {method:'POST', body: JSON.stringify({url: $('url').value})});
  const d = await r.json();
  if (d.error){ $('job').hidden = false; $('bar').hidden = true; $('note').hidden = true;
    $('stage').innerHTML = ''; $('stage').append(Object.assign(document.createElement('span'), {className:'err', textContent:d.error})); return; }
  poll();
};
$('quit').onclick = async () => {
  await fetch('/quit', {method:'POST'}).catch(() => {});
  document.body.innerHTML = '<main><h1>Setlist ID</h1><p class=lead>Closed. You can close this tab. Double-click Setlist ID to start it again.</p></main>';
};
poll();
</script></body></html>"""


def main() -> None:
    url = f"http://127.0.0.1:{PORT}/"
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError:  # already running – just open it
        webbrowser.open(url)
        return
    print(f"Setlist ID is running at {url}\nKeep this window open while you use it. Close it (or press Quit in the page) to stop.", flush=True)
    threading.Timer(0.5, webbrowser.open, args=(url,)).start()
    server.serve_forever()


if __name__ == "__main__":
    main()
