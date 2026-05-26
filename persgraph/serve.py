#!/usr/bin/env python3
"""
Financial Dashboard Server
Run: python3 serve.py
Open: http://localhost:8765
"""
import http.server, subprocess, os, json, urllib.parse, shutil
from pathlib import Path

PORT = 8765
FINANCE_DIR = Path(__file__).parent
SCRIPTS = {
    "2025":      FINANCE_DIR / "analyze_2025.py",
    "2026":      FINANCE_DIR / "analyze_transactions.py",
    "yoy":       FINANCE_DIR / "analyze_yoy.py",
    "portfolio": FINANCE_DIR / "analyze_portfolio.py",
}

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FINANCE_DIR), **kwargs)

    def do_GET(self):
        if self.path == "/" or self.path == "/dashboard":
            self.path = "/dashboard.html"
        super().do_GET()

    def do_POST(self):
        if self.path == "/api/refresh":
            # Parse which report(s) to refresh
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b'{"report":"all"}')
            report = body.get("report", "all")

            results = {}
            scripts_to_run = SCRIPTS.items() if report == "all" else [(report, SCRIPTS.get(report))]

            for name, script in scripts_to_run:
                if script and script.exists():
                    result = subprocess.run(
                        ["python3", str(script)],
                        capture_output=True, text=True, cwd=str(FINANCE_DIR)
                    )
                    results[name] = {
                        "ok": result.returncode == 0,
                        "msg": result.stdout[-200:] if result.stdout else result.stderr[-200:]
                    }
                else:
                    results[name] = {"ok": False, "msg": f"Script not found: {script}"}

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(results).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress request logs

if __name__ == "__main__":
    os.chdir(FINANCE_DIR)
    print(f"🚀 Financial Dashboard running at http://localhost:{PORT}")
    print(f"   Press Ctrl+C to stop")
    http.server.HTTPServer(("", PORT), Handler).serve_forever()
