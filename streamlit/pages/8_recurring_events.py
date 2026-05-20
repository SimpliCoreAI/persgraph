"""🔁 Recurring Events — Manage scheduled tasks and API cost tracking."""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import json
import streamlit as st
from datetime import date, timedelta
from pathlib import Path

st.set_page_config(page_title="Recurring Events", page_icon="🔁", layout="wide")
st.title("🔁 Recurring Events")
st.caption("Scheduled checks, reminders, and API cost tracking.")
st.divider()

tab1, tab2, tab3 = st.tabs(["📅 Upcoming Appointments", "💰 API Costs", "⚙️ Scheduled Jobs"])

# ── Tab 1: Upcoming Appointments ──────────────────────────────────────────────
with tab1:
    st.markdown("### 📅 Upcoming Appointments")

    try:
        from second_brain.notes import list_all

        days_ahead = st.slider("Show appointments within (days)", 1, 30, 7)
        today = date.today()
        cutoff = today + timedelta(days=days_ahead)

        appointments = list_all(item_type="Appointment", limit=200)
        upcoming = []
        for appt in appointments:
            date_str = appt.get("date", "").strip()
            if not date_str:
                continue
            try:
                appt_date = date.fromisoformat(date_str)
                if today <= appt_date <= cutoff:
                    days_away = (appt_date - today).days
                    upcoming.append({**appt, "days_away": days_away})
            except ValueError:
                continue

        upcoming.sort(key=lambda x: x["date"])

        if not upcoming:
            st.info(f"No appointments in the next {days_ahead} days.")
        else:
            for appt in upcoming:
                days_away = appt["days_away"]
                label = "🔴 Today" if days_away == 0 else "🟡 Tomorrow" if days_away == 1 else f"🟢 In {days_away} days"
                with st.expander(f"{label} · **{appt['title']}** · 📆 {appt['date']}"):
                    if appt.get("body"):
                        st.write(appt["body"])
                    st.caption(f"Tags: {appt.get('tags') or '—'}")

    except Exception as e:
        st.error(f"Could not load appointments: {e}")

# ── Tab 2: API Costs ──────────────────────────────────────────────────────────
with tab2:
    st.markdown("### 💰 API Cost Tracker")
    st.caption("Daily spend on Claude API (Anthropic). Updated via OpenClaw heartbeat.")

    data_file = Path(__file__).parent.parent.parent / "data" / "api_costs.json"

    if not data_file.exists():
        st.info("No cost data yet. OpenClaw will start logging on the next heartbeat.")
    else:
        try:
            with open(data_file) as f:
                data = json.load(f)

            # Total metrics
            total = data.get("total", {})
            col1, col2, col3 = st.columns(3)
            col1.metric("Total spend", f"${total.get('cost_usd', 0):.4f}")
            col2.metric("Total input tokens", f"{total.get('input_tokens', 0):,}")
            col3.metric("Total output tokens", f"{total.get('output_tokens', 0):,}")

            st.divider()

            # Daily breakdown
            st.markdown("#### Last 7 Days")
            daily = data.get("daily", {})
            today = date.today()
            rows = []
            for i in range(7):
                d = (today - timedelta(days=i)).isoformat()
                day_data = daily.get(d, {})
                rows.append({
                    "Date": d,
                    "Cost ($)": f"${day_data.get('cost_usd', 0):.4f}",
                    "Input tokens": f"{day_data.get('input_tokens', 0):,}",
                    "Output tokens": f"{day_data.get('output_tokens', 0):,}",
                    "API calls": day_data.get("calls", 0),
                })
            st.table(rows)

        except Exception as e:
            st.error(f"Could not read cost data: {e}")

# ── Tab 3: Scheduled Jobs ─────────────────────────────────────────────────────
with tab3:
    st.markdown("### ⚙️ Scheduled Jobs")
    st.caption("Managed via OpenClaw heartbeat and cron.")

    jobs = [
        {
            "name": "Appointment Reminders",
            "schedule": "Every heartbeat (~1h)",
            "action": "Check ChromaDB for appointments within 48h → Telegram alert",
            "status": "🟢 Active",
        },
        {
            "name": "Daily API Cost Summary",
            "schedule": "Daily ~8:00 PM",
            "action": "Log token usage → send Telegram summary",
            "status": "🟢 Active",
        },
        {
            "name": "Weekly Briefing",
            "schedule": "Sunday 8:00 AM",
            "action": "Generate digest → Telegram + Email",
            "status": "🔲 Planned",
        },
        {
            "name": "ChromaDB Health Check",
            "schedule": "Every heartbeat (~1h)",
            "action": "Ping ChromaDB + Ollama → alert if unreachable",
            "status": "🔲 Planned",
        },
    ]

    for job in jobs:
        with st.expander(f"{job['status']} · **{job['name']}** · {job['schedule']}"):
            st.write(job["action"])
