"""
PersGraph Web Server — serves HTML tools behind a login page.
Run: .venv/bin/python server.py
"""
import os
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, redirect, render_template_string, request, session, url_for, abort, jsonify

import json
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "pgraph-secret-change-me-xk29zq")
app.permanent_session_lifetime = 60 * 60 * 8  # 8 hours

BASE_DIR = Path(__file__).parent
os.makedirs(BASE_DIR / 'data', exist_ok=True)
NOTES_FILE = BASE_DIR / 'data' / 'travel_notes.json'
USERNAME = os.getenv("APP_USERNAME", "jolly")
PASSWORD = os.getenv("APP_PASSWORD", "persgraph2026")

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
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

@app.route("/")
@login_required
def index():
    hub_path = BASE_DIR / "templates" / "hub.html"
    if hub_path.exists():
        return hub_path.read_text()
    return redirect(url_for("travel"))

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if request.form.get("username") == USERNAME and request.form.get("password") == PASSWORD:
            session.permanent = True
            session["logged_in"] = True
            return redirect(url_for("index"))
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
