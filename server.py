"""
PersGraph Web Server — serves HTML tools behind a login page.
Run: .venv/bin/python server.py
"""
import os
import re
import html
from functools import wraps
from pathlib import Path
from urllib.parse import quote, unquote

from dotenv import load_dotenv
from flask import Flask, redirect, render_template_string, request, session, url_for, abort, jsonify

import json
load_dotenv()

app = Flask(__name__)
# SECURITY: Flask secret key must be set via FLASK_SECRET env var. Never use a default in production.
if not os.getenv("FLASK_SECRET"):
    raise ValueError("FLASK_SECRET environment variable is required. Set it to a secure random string.")
app.secret_key = os.getenv("FLASK_SECRET")
app.permanent_session_lifetime = 60 * 60 * 8  # 8 hours
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

BASE_DIR = Path(__file__).parent
os.makedirs(BASE_DIR / 'data', exist_ok=True)
NOTES_FILE = BASE_DIR / 'data' / 'travel_notes.json'
OBSIDIAN_VAULT = Path('/root/AgenticHub/InsightsData').expanduser()
# SECURITY: Credentials must be set via environment variables. No defaults allowed.
if not os.getenv("APP_USERNAME") or not os.getenv("APP_PASSWORD"):
    raise ValueError("APP_USERNAME and APP_PASSWORD environment variables are required.")
USERNAME = os.getenv("APP_USERNAME")
PASSWORD = os.getenv("APP_PASSWORD")

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PersGraph — Sign In</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: #080b14; color: #e2e8f0;
    font-family: 'Inter', -apple-system, sans-serif;
    min-height: 100vh; display: flex; align-items: center; justify-content: center;
  }
  .card {
    background: #0d1120; border: 1px solid rgba(99,179,237,0.12);
    border-radius: 16px; padding: 2.5rem; width: 100%; max-width: 380px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.4);
  }
  .logo { font-size: 1.5rem; font-weight: 700; margin-bottom: 0.25rem;
    background: linear-gradient(135deg, #63b3ed, #9f7aea);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
  .subtitle { color: #64748b; font-size: 0.875rem; margin-bottom: 2rem; }
  label { display: block; font-size: 0.8rem; color: #94a3b8; margin-bottom: 0.4rem; }
  input {
    width: 100%; padding: 0.65rem 0.9rem; background: #111827;
    border: 1px solid rgba(99,179,237,0.15); border-radius: 8px;
    color: #e2e8f0; font-size: 0.95rem; font-family: inherit;
    margin-bottom: 1.1rem; outline: none; transition: border-color 0.2s;
  }
  input:focus { border-color: #63b3ed; }
  button {
    width: 100%; padding: 0.7rem; background: #63b3ed; color: #080b14;
    border: none; border-radius: 8px; font-size: 0.95rem; font-weight: 600;
    font-family: inherit; cursor: pointer; transition: opacity 0.2s;
  }
  button:hover { opacity: 0.88; }
  .error {
    background: rgba(252,129,74,0.1); border: 1px solid rgba(252,129,74,0.3);
    color: #fc814a; border-radius: 8px; padding: 0.6rem 0.9rem;
    font-size: 0.85rem; margin-bottom: 1.1rem;
  }
</style>
</head>
<body>
<div class="card">
  <div class="logo">🔒 PersGraph</div>
  <div class="subtitle">Sign in to continue</div>
  {% if error %}<div class="error">{{ error }}</div>{% endif %}
  <form method="post">
    <label>Username</label>
    <input type="text" name="username" autocomplete="username" autofocus>
    <label>Password</label>
    <input type="password" name="password" autocomplete="current-password">
    <button type="submit">Sign in</button>
  </form>
</div>
</body>
</html>
"""

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # Trust Caddy's basic_auth — if Authorization header exists, user is authenticated
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Basic "):
            # Caddy has already authenticated via basic_auth
            session.permanent = True
            session["logged_in"] = True
        
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

@app.route("/")
def index():
    marketing_path = BASE_DIR / "marketing" / "persgraph-landing.html"
    if marketing_path.exists():
        return marketing_path.read_text()
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    # Caddy already handles public auth; this page should only be a lightweight entry page.
    # If the session is already set, go straight to the app.
    if session.get("logged_in"):
        return redirect(url_for("index"))

    error = None
    if request.method == "POST":
        # Preserve backward compatibility, but avoid looping if proxy auth already happened.
        if request.form.get("username") == USERNAME and request.form.get("password") == PASSWORD:
            session.permanent = True
            session["logged_in"] = True
            return redirect(url_for("travel"), code=303)
        error = "Invalid username or password."
    return render_template_string(LOGIN_HTML, error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/travel")
@login_required
def travel():
    html_path = BASE_DIR / "travel" / "index.html"
    if not html_path.exists():
        abort(404)
    return html_path.read_text()

@app.route("/debrief")
@login_required
def debrief():
    tmpl = BASE_DIR / "templates" / "debrief.html"
    if not tmpl.exists():
        abort(404)
    return tmpl.read_text()

@app.route("/api/debrief")
@login_required
def api_debrief():
    period = request.args.get("period", "week")
    debrief_file = BASE_DIR / "data" / "debrief.json"
    if not debrief_file.exists():
        return jsonify({"empty": True, "period": period})
    data = json.loads(debrief_file.read_text())
    return jsonify(data)

@app.route("/api/debrief/generate", methods=["POST"])
@login_required
def api_debrief_generate():
    import subprocess, sys
    period = request.get_json(force=True).get("period", "week")
    try:
        subprocess.Popen(
            [sys.executable, str(BASE_DIR / "scripts" / "debrief.py"), period],
            cwd=str(BASE_DIR)
        )
        return jsonify({"ok": True, "message": f"Debrief generation started for period: {period}"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/langfuse")
@login_required
def api_langfuse():
    """Health/status proxy for Langfuse connectivity and config."""
    try:
        import httpx
        from second_brain.config import settings

        host = settings.langfuse_host.rstrip("/")
        headers = {}
        if settings.langfuse_secret_key:
            headers["Authorization"] = f"Bearer {settings.langfuse_secret_key}"

        # Prefer the lightweight health endpoint; fall back to a simple HEAD/GET on the root.
        for path in ("/api/public/health", "/api/health", "/health", ""):
            url = f"{host}{path}"
            try:
                response = httpx.get(url, headers=headers, timeout=10.0)
                if response.status_code == 404:
                    continue
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    payload = response.json()
                else:
                    payload = {"ok": True, "status_code": response.status_code, "body": response.text[:500]}
                payload.setdefault("endpoint", path or "/")
                payload.setdefault("host", host)
                return jsonify(payload)
            except httpx.HTTPStatusError as exc:
                return jsonify({"ok": False, "host": host, "endpoint": path or "/", "status_code": exc.response.status_code, "error": str(exc)}), 502

        return jsonify({"ok": False, "host": host, "error": "No Langfuse health endpoint responded"}), 502
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/static/<path:filename>")
@login_required
def static_files(filename):
    # Resolve safely — no path traversal
    for subdir in ("travel", "persgraph", "marketing"):
        candidate = (BASE_DIR / subdir / filename).resolve()
        if candidate.exists() and BASE_DIR in candidate.parents:
            return candidate.read_bytes(), 200, {"Content-Type": _mime(filename)}
    abort(404)

def _mime(filename):
    ext = Path(filename).suffix.lower()
    return {
        ".html": "text/html",
        ".css": "text/css",
        ".js": "application/javascript",
        ".json": "application/json",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".svg": "image/svg+xml",
        ".woff": "font/woff",
        ".woff2": "font/woff2",
        ".ttf": "font/ttf"
    }.get(ext, "application/octet-stream")



def _safe_note_relpath(raw_path: str) -> Path:
    rel = Path(unquote(raw_path))
    if rel.is_absolute() or ".." in rel.parts:
        abort(404)
    full = (OBSIDIAN_VAULT / rel).resolve()
    vault = OBSIDIAN_VAULT.resolve()
    if vault != full and vault not in full.parents:
        abort(404)
    return full


def _note_title(path: Path) -> str:
    return path.stem.replace("-", " ").replace("_", " ").strip() or path.name


def _list_vault_notes():
    if not OBSIDIAN_VAULT.exists():
        return []
    notes = []
    for path in OBSIDIAN_VAULT.rglob("*.md"):
        if any(part.startswith('.') for part in path.relative_to(OBSIDIAN_VAULT).parts):
            continue
        rel = path.relative_to(OBSIDIAN_VAULT)
        parent = str(rel.parent) if str(rel.parent) != "." else "Root"
        notes.append({
            "path": rel.as_posix(),
            "title": _note_title(path),
            "folder": parent,
            "mtime": path.stat().st_mtime,
        })
    notes.sort(key=lambda n: (-n["mtime"], n["title"].lower()))
    return notes


def _markdown_to_html(text: str) -> str:
    lines = text.replace("\r\n", "\n").split("\n")
    out = []
    in_ul = False
    in_ol = False
    in_code = False
    code_lines = []
    i = 0

    def close_lists():
        nonlocal in_ul, in_ol
        if in_ul:
            out.append("</ul>")
            in_ul = False
        if in_ol:
            out.append("</ol>")
            in_ol = False

    def inline_format(s: str) -> str:
        s = html.escape(s)
        s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
        s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
        s = re.sub(r'\*(.+?)\*', r'<em>\1</em>', s)
        return s

    while i < len(lines):
        line = lines[i]

        if line.strip().startswith("```"):
            close_lists()
            if in_code:
                out.append("<pre><code>{}</code></pre>".format(html.escape("\n".join(code_lines))))
                in_code = False
                code_lines = []
            else:
                in_code = True
                code_lines = []
            i += 1
            continue

        if in_code:
            code_lines.append(line)
            i += 1
            continue

        stripped = line.strip()
        callout = re.match(r'^>\s*\[!(\w+)\]([+-])?\s*(.*)$', stripped)
        if callout:
            close_lists()
            ctype = callout.group(1).lower()
            collapse_flag = callout.group(2) or ''
            title = callout.group(3).strip() or ctype.title()
            open_attr = '' if collapse_flag == '-' else ' open'
            body_lines = []
            i += 1
            while i < len(lines):
                nxt = lines[i]
                if nxt.startswith('> [!'):
                    break
                if nxt.startswith('>'):
                    body_lines.append(re.sub(r'^>\s?', '', nxt))
                    i += 1
                    continue
                if nxt.strip() == '':
                    next_nonempty = None
                    j = i + 1
                    while j < len(lines):
                        if lines[j].strip():
                            next_nonempty = lines[j]
                            break
                        j += 1
                    if next_nonempty is not None and not next_nonempty.startswith('> [!') and next_nonempty.startswith('>'):
                        body_lines.append('')
                        i += 1
                        continue
                break
            body_html = _markdown_to_html("\n".join(body_lines).strip()) if any(x.strip() for x in body_lines) else ''
            out.append(
                f'<details class="callout callout-{ctype}"{open_attr}>'
                f'<summary>{inline_format(title)}</summary>'
                f'<div class="callout-body">{body_html}</div>'
                f'</details>'
            )
            continue

        if not stripped:
            close_lists()
            i += 1
            continue

        m = re.match(r'^(#{1,6})\s+(.*)$', stripped)
        if m:
            close_lists()
            level = len(m.group(1))
            out.append(f"<h{level}>{inline_format(m.group(2))}</h{level}>")
            i += 1
            continue

        if re.match(r'^[-*]\s+', stripped):
            if in_ol:
                out.append("</ol>")
                in_ol = False
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            item = re.sub(r'^[-*]\s+', '', stripped)
            out.append(f"<li>{inline_format(item)}</li>")
            i += 1
            continue

        if re.match(r'^\d+\.\s+', stripped):
            if in_ul:
                out.append("</ul>")
                in_ul = False
            if not in_ol:
                out.append("<ol>")
                in_ol = True
            item = re.sub(r'^\d+\.\s+', '', stripped)
            out.append(f"<li>{inline_format(item)}</li>")
            i += 1
            continue

        close_lists()
        out.append(f"<p>{inline_format(stripped)}</p>")
        i += 1

    if in_code:
        out.append("<pre><code>{}</code></pre>".format(html.escape("\n".join(code_lines))))
    close_lists()
    return "\n".join(out)


def _render_notes_index(notes, query):
    query_value = html.escape(query or "")
    total = len(notes)
    folders = sorted({n["folder"] for n in notes})
    folder_html = "".join(
        f'<span class="pill">{html.escape(folder)}</span>' for folder in folders[:18]
    ) or '<span class="muted">No folders yet</span>'

    note_cards = []
    for note in notes[:250]:
        href = f"/notes/view/{quote(note['path'])}"
        note_cards.append(
            f'<a class="note-card" href="{href}"><div class="note-title">{html.escape(note["title"])}</div><div class="note-meta">{html.escape(note["folder"])}</div></a>'
        )
    notes_html = "\n".join(note_cards) or '<div class="empty">No notes matched.</div>'

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Notes Vault</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {{ --bg:#080b14; --card:#0d1120; --card2:#111827; --border:rgba(99,179,237,.12); --border2:rgba(99,179,237,.25); --txt:#e2e8f0; --mut:#94a3b8; --a1:#63b3ed; --r:14px; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:Inter,sans-serif; background:var(--bg); color:var(--txt); }}
    .wrap {{ max-width:1120px; margin:0 auto; padding:28px 18px 60px; }}
    .topbar {{ display:flex; justify-content:space-between; gap:16px; align-items:flex-start; flex-wrap:wrap; margin-bottom:20px; }}
    .title {{ font-size:28px; font-weight:800; }}
    .subtitle {{ color:var(--mut); margin-top:6px; }}
    .back {{ color:var(--a1); text-decoration:none; font-weight:600; }}
    .panel {{ background:linear-gradient(135deg,var(--card),var(--card2)); border:1px solid var(--border); border-radius:var(--r); padding:18px; margin-bottom:18px; }}
    .search {{ display:flex; gap:12px; flex-wrap:wrap; align-items:center; }}
    input[type=text] {{ flex:1; min-width:240px; background:#0a1220; color:var(--txt); border:1px solid var(--border2); border-radius:10px; padding:12px 14px; font:inherit; }}
    button {{ background:var(--a1); color:#081018; border:none; border-radius:10px; padding:12px 16px; font:inherit; font-weight:700; cursor:pointer; }}
    .meta {{ display:flex; gap:10px; flex-wrap:wrap; align-items:center; color:var(--mut); margin-top:14px; }}
    .pill {{ display:inline-flex; padding:6px 10px; border-radius:999px; background:rgba(99,179,237,.10); border:1px solid rgba(99,179,237,.18); color:#cfe7ff; font-size:12px; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:14px; }}
    .note-card {{ text-decoration:none; color:inherit; background:linear-gradient(135deg,var(--card),var(--card2)); border:1px solid var(--border); border-radius:12px; padding:16px; min-height:110px; display:flex; flex-direction:column; justify-content:space-between; transition:.2s ease; }}
    .note-card:hover {{ border-color:var(--border2); transform:translateY(-2px); }}
    .note-title {{ font-size:16px; font-weight:700; line-height:1.35; }}
    .note-meta {{ color:var(--mut); font-size:13px; margin-top:12px; }}
    .empty {{ color:var(--mut); padding:18px 4px; }}
    .muted {{ color:var(--mut); }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="topbar">
      <div>
        <div class="title">📝 Notes Vault</div>
        <div class="subtitle">Browse Obsidian notes from {html.escape(str(OBSIDIAN_VAULT))}</div>
      </div>
      <a class="back" href="/">← Back to Hub</a>
    </div>

    <div class="panel">
      <form class="search" method="get" action="/notes">
        <input type="text" name="q" value="{query_value}" placeholder="Search note titles…">
        <button type="submit">Search</button>
      </form>
      <div class="meta">
        <span>{total} note{'s' if total != 1 else ''}</span>
        <span>·</span>
        <span>Folder view + title search</span>
      </div>
    </div>

    <div class="panel">
      <div class="meta" style="margin-top:0">{folder_html}</div>
    </div>

    <div class="grid">{notes_html}</div>
  </div>
</body>
</html>
"""


def _render_note_page(rel_path: str, raw_markdown: str):
    body = _markdown_to_html(raw_markdown)
    title = html.escape(_note_title(Path(rel_path)))
    rel_escaped = html.escape(rel_path)
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {{ --bg:#080b14; --card:#0d1120; --card2:#111827; --border:rgba(99,179,237,.12); --border2:rgba(99,179,237,.25); --txt:#e2e8f0; --mut:#94a3b8; --a1:#63b3ed; --r:14px; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:Inter,sans-serif; background:var(--bg); color:var(--txt); }}
    .wrap {{ max-width:900px; margin:0 auto; padding:28px 18px 60px; }}
    .crumbs {{ display:flex; justify-content:space-between; gap:14px; flex-wrap:wrap; margin-bottom:18px; }}
    .crumbs a {{ color:var(--a1); text-decoration:none; font-weight:600; }}
    .muted {{ color:var(--mut); }}
    .card {{ background:linear-gradient(135deg,var(--card),var(--card2)); border:1px solid var(--border); border-radius:var(--r); padding:24px; }}
    h1,h2,h3,h4,h5,h6 {{ line-height:1.25; margin:1.2em 0 .5em; }}
    h1:first-child {{ margin-top:0; font-size:34px; }}
    p, li {{ color:#dbe6f4; font-size:16px; line-height:1.7; }}
    p {{ margin:0 0 14px; }}
    ul, ol {{ padding-left:24px; margin:0 0 14px; }}
    code {{ background:#0a1220; padding:2px 6px; border-radius:6px; font-size:.92em; }}
    pre {{ background:#0a1220; border:1px solid var(--border); padding:14px; border-radius:10px; overflow:auto; margin:0 0 14px; }}
    pre code {{ background:none; padding:0; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="crumbs">
      <div>
        <a href="/">Hub</a>
        <span class="muted"> · </span>
        <a href="/notes">Notes</a>
      </div>
      <div class="muted">{rel_escaped}</div>
    </div>
    <div class="card">{body}</div>
  </div>
</body>
</html>
"""


@app.route("/notes")
@login_required
def notes_index():
    query = (request.args.get("q") or "").strip().lower()
    notes = _list_vault_notes()
    if query:
        notes = [n for n in notes if query in n["title"].lower() or query in n["path"].lower()]
    return _render_notes_index(notes, request.args.get("q") or "")


@app.route("/notes/view/<path:note_path>")
@login_required
def notes_view(note_path):
    full = _safe_note_relpath(note_path)
    if not full.exists() or not full.is_file() or full.suffix.lower() != ".md":
        abort(404)
    rel = full.relative_to(OBSIDIAN_VAULT).as_posix()
    return _render_note_page(rel, full.read_text())

@app.route("/api/notes", methods=["GET"])
@login_required
def get_notes():
    if NOTES_FILE.exists():
        return jsonify({"notes": json.loads(NOTES_FILE.read_text())})
    return jsonify({"notes": {}})

@app.route("/api/notes", methods=["POST"])
@login_required
def save_note():
    data = request.get_json(force=True)
    key, value = data.get("key"), data.get("value")
    if not key:
        return jsonify({"ok": False, "error": "missing key"}), 400
    notes = json.loads(NOTES_FILE.read_text()) if NOTES_FILE.exists() else {}
    notes[key] = value
    NOTES_FILE.write_text(json.dumps(notes, indent=2))
    return jsonify({"ok": True})

if __name__ == "__main__":
    print("PersGraph Web Server starting on http://0.0.0.0:8766")
    app.run(host="0.0.0.0", port=8766, debug=False)
