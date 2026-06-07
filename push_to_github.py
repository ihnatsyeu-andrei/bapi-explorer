import urllib.request, urllib.error, json, os, base64, sys

TOKEN = os.environ["GH_API_TOKEN"]
OWNER = "ihnatsyeu-andrei"
REPO  = "bapi-explorer"
BASE  = f"https://api.github.com/repos/{OWNER}/{REPO}"
HDR = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github+json",
    "User-Agent": "bapi-explorer-setup",
    "Content-Type": "application/json",
}

MSG = """Initial commit: BAPI Explorer v1.0

FastAPI + pyrfc web app for exploring and executing SAP RFC function modules.

Features:
- Wildcard search with group filter, instant filter, pagination, recent searches
- Structure tab with type drill-down, parameter filter, copy field name
- Run tab with auto-generated form, fill skeleton, raw JSON override, input persistence
- Result tab with status, BAPIRET2 messages, JSON copy, CSV export
- Run history (per BAPI, last 20 runs, replay support)
- Multi-system profiles via profiles.json + navbar switcher
- AI assistant via GitHub Copilot SDK (streaming SSE, SAP context-aware)
- Light / Dark / System theme switcher (Bootstrap 5.3 data-bs-theme)
- Fully offline - Bootstrap 5.3.3 + Icons bundled (no CDN)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"""

def api(method, url, data=None):
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=HDR, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        txt = e.read().decode()
        print(f"HTTP {e.code} {method} {url}: {txt[:200]}")
        sys.exit(1)

SKIP_DIRS  = {".git", ".venv", "venv", "__pycache__"}
SKIP_FILES = {".env", "profiles.json", "dev_rfc.log", "push_to_github.py"}
SKIP_EXT   = {".pyc", ".pyo", ".log"}

files = []
for root, dirs, filenames in os.walk("."):
    dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
    for f in filenames:
        if f in SKIP_FILES: continue
        if any(f.endswith(e) for e in SKIP_EXT): continue
        fpath = os.path.join(root, f)
        relpath = fpath.replace("\\", "/").lstrip("./")
        files.append((relpath, fpath))

print(f"Uploading {len(files)} files via Contents API...")
for i, (relpath, fpath) in enumerate(files, 1):
    with open(fpath, "rb") as fh:
        raw = fh.read()
    encoded = base64.b64encode(raw).decode()
    data = {"message": MSG if i == 1 else f"chore: add {relpath}", "content": encoded, "branch": "main"}
    api("PUT", f"{BASE}/contents/{relpath}", data)
    print(f"  [{i}/{len(files)}] {relpath}")

print(f"\nDone! https://github.com/{OWNER}/{REPO}")
