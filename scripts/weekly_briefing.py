"""
Weekly Briefing Agent for PersGraph
====================================
ADK-inspired state machine pattern: explicit state schema, idempotent steps,
survives restarts.

Usage:
    python scripts/weekly_briefing.py          # skips if already run today
    python scripts/weekly_briefing.py --force  # re-runs regardless
"""

import argparse
import datetime
import json
import os
import socket
import sqlite3
import sys

# Resolve project root relative to this script
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from second_brain.briefing_state import BriefingStateManager, BriefingStep
from second_brain import learning_db

STATE_PATH = os.path.join(BASE_DIR, "data", "briefing_state.json")
DB_PATH = os.path.join(BASE_DIR, "data", "notes.db")
BRIEFING_OUTPUT = os.path.join(BASE_DIR, "data", "last_briefing.txt")

CHROMADB_HOST = os.getenv("CHROMA_HOST", "localhost")  # Load from config/env
CHROMADB_PORT = 8000

# ---------------------------------------------------------------------------
# Hardcoded rotating content
# ---------------------------------------------------------------------------

QUOTES = [
    "\"The best way to predict the future is to invent it.\" — Alan Kay",
    "\"Simplicity is the soul of efficiency.\" — Austin Freeman",
    "\"First, solve the problem. Then, write the code.\" — John Johnson",
    "\"Code is like humor. When you have to explain it, it's bad.\" — Cory House",
    "\"Any fool can write code that a computer can understand. Good programmers write code that humans can understand.\" — Martin Fowler",
    "\"Make it work, make it right, make it fast.\" — Kent Beck",
    "\"The most disastrous thing that you can ever learn is your first programming language.\" — Alan Kay",
    "\"Programs must be written for people to read, and only incidentally for machines to execute.\" — Harold Abelson",
    "\"Walking on water and developing software from a specification are easy if both are frozen.\" — Edward V. Berard",
    "\"The function of good software is to make the complex appear to be simple.\" — Grady Booch",
]

JOKES = [
    "Why do programmers prefer dark mode? Because light attracts bugs! 🐛",
    "A SQL query walks into a bar, walks up to two tables and asks... 'Can I join you?' 🍺",
    "How many programmers does it take to change a light bulb? None — that's a hardware problem. 💡",
    "Why do Java developers wear glasses? Because they don't C#! 👓",
    "There are 10 types of people in the world: those who understand binary, and those who don't. 🔢",
]


# ---------------------------------------------------------------------------
# Step implementations
# ---------------------------------------------------------------------------

def collect(state_mgr: BriefingStateManager) -> dict:
    """COLLECTING: gather tasks, appointments, and system health from local sources."""
    state_mgr.transition(BriefingStep.COLLECTING)
    collected = {}

    # --- Tasks ---
    tasks = []
    if os.path.exists(DB_PATH):
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute(
                """
                SELECT title, tags, created_at
                FROM notes
                WHERE tags LIKE '%task%'
                  AND title NOT IN (
                    'help', 'list', '--list',
                    'list --status open', 'test langfuse trace'
                  )
                ORDER BY created_at DESC
                LIMIT 20
                """
            )
            rows = cur.fetchall()
            conn.close()
            for title, tags, created_at in rows:
                tasks.append({
                    "title": title,
                    "tags": tags,
                    "created_at": created_at,
                })
        except sqlite3.Error as e:
            tasks = [{"error": str(e)}]
    else:
        tasks = []  # DB not found — gracefully empty

    collected["tasks"] = tasks

    # --- Explore Mode Feedback ---
    explore_feedback = {}
    try:
        outcomes = learning_db.get_outcome_summary(limit=50)
        if outcomes:
            counts = {}
            for outcome in outcomes:
                otype = outcome.get("outcome_type", "unknown")
                counts[otype] = counts.get(otype, 0) + 1
            explore_feedback["outcome_counts"] = counts
            explore_feedback["recent_outcomes"] = outcomes[:10]
        else:
            explore_feedback["outcome_counts"] = {}
            explore_feedback["recent_outcomes"] = []
    except Exception as e:
        explore_feedback["error"] = str(e)
    
    collected["explore_feedback"] = explore_feedback

    # --- Appointments ---
    appointments = []
    if os.path.exists(DB_PATH):
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute(
                """
                SELECT title, tags, created_at
                FROM notes
                WHERE tags LIKE '%appointment%'
                   OR tags LIKE '%calendar%'
                ORDER BY created_at DESC
                LIMIT 10
                """
            )
            rows = cur.fetchall()
            conn.close()
            for title, tags, created_at in rows:
                appointments.append({
                    "title": title,
                    "tags": tags,
                    "created_at": created_at,
                })
        except sqlite3.Error as e:
            appointments = [{"error": str(e)}]
    else:
        appointments = []

    collected["appointments"] = appointments

    # --- System health: ChromaDB reachability ---
    chromadb_online = False
    try:
        with socket.create_connection((CHROMADB_HOST, CHROMADB_PORT), timeout=3):
            chromadb_online = True
    except (OSError, socket.timeout):
        chromadb_online = False

    collected["system_health"] = {
        "chromadb_online": chromadb_online,
        "chromadb_host": f"{CHROMADB_HOST}:{CHROMADB_PORT}",
        "hostname": socket.gethostname(),
    }

    # Persist collected data
    state_mgr.transition(BriefingStep.COLLECTING, collected=collected)
    return collected


def get_api_cost_summary() -> dict:
    """Pull recent API cost data for briefing."""
    cost_file = os.path.join(BASE_DIR, "data", "api_costs.json")
    try:
        if not os.path.exists(cost_file):
            return {"total": {"cost_usd": 0.0}, "daily": {}}
        with open(cost_file) as f:
            data = json.load(f)
        return data
    except Exception as e:
        import logging
        logging.warning(f"Could not load cost data: {e}")
        return {"total": {"cost_usd": 0.0}, "daily": {}}


def compose(state_mgr: BriefingStateManager, collected: dict, week_number: int) -> str:
    """COMPOSING: build the formatted briefing string."""
    state_mgr.transition(BriefingStep.COMPOSING)

    quote = QUOTES[week_number % len(QUOTES)]
    joke = JOKES[week_number % len(JOKES)]

    today = datetime.date.today()
    lines = []

    lines.append("=" * 60)
    lines.append(f"  📋 WEEKLY BRIEFING — Week {week_number}  ({today.strftime('%A, %B %d %Y')})")
    lines.append("=" * 60)
    lines.append("")

    # --- Appointments ---
    lines.append("📅  Upcoming This Week")
    lines.append("-" * 40)
    appointments = collected.get("appointments") or []
    if not appointments:
        lines.append("  No upcoming appointments found.")
    else:
        for appt in appointments[:5]:
            if "error" in appt:
                lines.append(f"  ⚠️  Error fetching appointments: {appt['error']}")
                break
            lines.append(f"  • {appt['title']}  ({appt.get('created_at', '')})")
    lines.append("")

    # --- Tasks ---
    lines.append("✅  Open Tasks")
    lines.append("-" * 40)
    tasks = collected.get("tasks") or []

    deadline_keywords = ["deadline", "due", "urgent", "asap", "today", "tomorrow", "priority"]

    def has_deadline(t):
        combined = f"{t.get('title', '')} {t.get('tags', '')}".lower()
        return any(kw in combined for kw in deadline_keywords)

    if not tasks:
        lines.append("  No open tasks found.")
    else:
        # Errors
        if tasks and "error" in tasks[0]:
            lines.append(f"  ⚠️  Error fetching tasks: {tasks[0]['error']}")
        else:
            priority_tasks = [t for t in tasks if has_deadline(t)]
            other_tasks = [t for t in tasks if not has_deadline(t)]
            top_5 = (priority_tasks + other_tasks)[:5]
            for t in top_5:
                marker = "🔥" if has_deadline(t) else "  "
                lines.append(f"  {marker} {t['title']}  ({t.get('created_at', '')})")
            if len(tasks) > 5:
                lines.append(f"  … and {len(tasks) - 5} more task(s).")
    lines.append("")

    # --- Explore Mode Feedback Summary ---
    lines.append("🗺️   Explore Mode Feedback")
    lines.append("-" * 40)
    explore_feedback = collected.get("explore_feedback") or {}
    if "error" in explore_feedback:
        lines.append(f"  ⚠️  Error reading feedback: {explore_feedback['error']}")
    else:
        counts = explore_feedback.get("outcome_counts") or {}
        if counts:
            lines.append("  Outcomes this week:")
            for otype, count in sorted(counts.items()):
                icon = {"accepted": "✅", "skipped": "⏭️", "bookmarked": "⭐", "clicked": "🔗"}.get(otype, "📍")
                lines.append(f"    {icon} {otype}: {count}")
        else:
            lines.append("  No Explore feedback recorded yet.")
    lines.append("")

    # --- System Health ---
    lines.append("🖥️   System Health")
    lines.append("-" * 40)
    health = collected.get("system_health") or {}
    chromadb_status = "🟢 Online" if health.get("chromadb_online") else "🔴 Offline"
    lines.append(f"  ChromaDB ({health.get('chromadb_host', CHROMADB_HOST)}): {chromadb_status}")
    lines.append(f"  Hostname: {health.get('hostname', 'unknown')}")
    lines.append("")

    # --- API Cost Summary ---
    lines.append("💰  API Cost Summary")
    lines.append("-" * 40)
    cost_data = get_api_cost_summary()
    total_cost = cost_data.get("total", {}).get("cost_usd", 0.0)
    daily_costs = cost_data.get("daily", {})
    if daily_costs:
        sorted_dates = sorted(daily_costs.keys(), reverse=True)[:7]
        seven_day_total = sum(daily_costs.get(d, {}).get("cost_usd", 0.0) for d in sorted_dates)
        lines.append(f"  7-day total: ${seven_day_total:.2f}")
        if sorted_dates:
            today_cost = daily_costs.get(sorted_dates[0], {}).get("cost_usd", 0.0)
            lines.append(f"  Today ({sorted_dates[0]}): ${today_cost:.2f}")
    else:
        lines.append("  No cost data available yet.")
    lines.append(f"  All-time total: ${total_cost:.2f}")
    lines.append("")

    # --- Quote ---
    lines.append("💬  Quote of the Week")
    lines.append("-" * 40)
    lines.append(f"  {quote}")
    lines.append("")

    # --- Joke ---
    lines.append("😄  Dev Joke")
    lines.append("-" * 40)
    lines.append(f"  {joke}")
    lines.append("")
    lines.append("=" * 60)

    briefing = "\n".join(lines)
    state_mgr.transition(BriefingStep.COMPOSING, composed_briefing=briefing)
    return briefing


def deliver(state_mgr: BriefingStateManager, briefing: str, today_str: str):
    """DELIVERING: write briefing to file and print to stdout."""
    state_mgr.transition(BriefingStep.DELIVERING)

    os.makedirs(os.path.dirname(BRIEFING_OUTPUT), exist_ok=True)
    with open(BRIEFING_OUTPUT, "w") as f:
        f.write(briefing)
        f.write("\n")

    print(briefing)

    state_mgr.transition(
        BriefingStep.DONE,
        last_run_date=today_str,
        last_run_status="success",
        error=None,
    )


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_briefing(force: bool = False):
    state_mgr = BriefingStateManager(path=STATE_PATH)
    state = state_mgr.load()

    today = datetime.date.today()
    today_str = today.isoformat()
    week_number = today.isocalendar()[1]

    # Idempotency check
    if (
        not force
        and state.get("run_id") == today_str
        and state.get("current_step") == BriefingStep.DONE
    ):
        print(f"[weekly_briefing] Already completed for {today_str}. Use --force to re-run.")
        return

    # Initialize run
    state_mgr.transition(
        BriefingStep.IDLE,
        run_id=today_str,
        composed_briefing=None,
        error=None,
        collected={"appointments": None, "tasks": None, "system_health": None},
    )

    try:
        # Resume from last incomplete step if restarting mid-run
        state = state_mgr.load()
        current = state.get("current_step", BriefingStep.IDLE)

        if current in (BriefingStep.IDLE, BriefingStep.COLLECTING):
            collected = collect(state_mgr)
        else:
            collected = state.get("collected", {})  # Resume from saved state if available

        state = state_mgr.load()
        current = state.get("current_step", BriefingStep.COLLECTING)

        if current in (BriefingStep.COLLECTING, BriefingStep.COMPOSING):
            briefing = compose(state_mgr, collected, week_number)
        else:
            briefing = state.get("composed_briefing", "")

        state = state_mgr.load()
        current = state.get("current_step", BriefingStep.COMPOSING)

        if current in (BriefingStep.COMPOSING, BriefingStep.DELIVERING):
            deliver(state_mgr, briefing, today_str)

    except Exception as e:
        state_mgr.transition(BriefingStep.FAILED, error=str(e))
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PersGraph Weekly Briefing Agent")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-run even if already completed today",
    )
    args = parser.parse_args()
    run_briefing(force=args.force)
