"""📋 Weekly Briefing — Preview and manual trigger for weekly digest."""

import streamlit as st
import subprocess
import json
from datetime import datetime
from pathlib import Path

BASE = Path("/Users/jasleenkaur/AgenticHub/Persgraph")
STATE_FILE = BASE / "data/briefing_state.json"
BRIEFING_FILE = BASE / "data/last_briefing.txt"

st.set_page_config(page_title="Weekly Briefing", page_icon="📋", layout="wide")
st.title("📋 Weekly Briefing")
st.caption("Fires every Sunday at 8:00 AM · Delivered via Telegram + Email")
st.divider()

# ── Load state ────────────────────────────────────────────────────────────────
def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"current_step": "IDLE", "last_run_date": None, "last_run_status": None, "run_id": None}

state = load_state()

step = state.get("current_step", "IDLE")
last_run = state.get("last_run_date") or "—"
last_status = state.get("last_run_status") or "—"

step_emoji = {
    "IDLE": "💤",
    "COLLECTING": "🔍",
    "COMPOSING": "✍️",
    "DELIVERING": "📤",
    "DONE": "✅",
    "FAILED": "❌",
}.get(step, "❓")

# ── Status ────────────────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Schedule", "Sunday 8:00 AM")
with col2:
    st.metric("Current State", f"{step_emoji} {step}")
with col3:
    st.metric("Last Run", last_run)
with col4:
    status_icon = "✅" if last_status == "success" else ("❌" if last_status == "failed" else "—")
    st.metric("Last Status", f"{status_icon} {last_status}" if last_status != "—" else "—")

if step == "FAILED" and state.get("error"):
    st.error(f"❌ Last error: {state['error']}")

st.divider()

# ── Manual trigger ────────────────────────────────────────────────────────────
st.markdown("### 🚀 Manual Trigger")
col_btn1, col_btn2 = st.columns([1, 4])
with col_btn1:
    run_now = st.button("▶️ Run Now", type="primary")
with col_btn2:
    force = st.checkbox("Force re-run (even if already ran today)")

if run_now:
    cmd = ["python", "scripts/weekly_briefing.py"]
    if force:
        cmd.append("--force")
    with st.spinner("Running briefing agent..."):
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(BASE))
    if result.returncode == 0:
        st.success("✅ Briefing generated!")
        state = load_state()
    else:
        st.error(f"❌ Failed:\n```\n{result.stderr}\n```")

st.divider()

# ── Last briefing output ──────────────────────────────────────────────────────
st.markdown("### 📄 Last Briefing Output")
if BRIEFING_FILE.exists():
    content = BRIEFING_FILE.read_text()
    st.code(content, language=None)
    mtime = datetime.fromtimestamp(BRIEFING_FILE.stat().st_mtime)
    st.caption(f"Generated: {mtime.strftime('%A %b %d %Y at %I:%M %p')}")
else:
    st.info("No briefing generated yet. Hit ▶️ Run Now to generate one.")

st.divider()

# ── State inspector ───────────────────────────────────────────────────────────
with st.expander("🔍 Raw State (debug)"):
    st.json(state)
