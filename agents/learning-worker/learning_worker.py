"""
PersGraph Learning Worker — Batch Pattern Extractor
====================================================
Processes accumulated events/outcomes from learning.db and updates
skills and preferences based on detected patterns.

Trigger: cron every 30 minutes
Cursor: _meta table for idempotent processing

Usage:
    python scripts/learning_worker.py           # normal run
    python scripts/learning_worker.py --dry-run # preview only, no writes
    python scripts/learning_worker.py --force   # reprocess all records
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from second_brain import learning_db

EPOCH = "1970-01-01T00:00:00+00:00"
EVENT_CURSOR_KEY = "learning_worker_last_event_cursor"
OUTCOME_CURSOR_KEY = "learning_worker_last_outcome_cursor"
LAST_RUN_KEY = "learning_worker_last_run"
MIN_SIGNALS = 3


# ---------------------------------------------------------------------------
# Cursor helpers
# ---------------------------------------------------------------------------

def _get_cursor(key: str) -> str:
    return learning_db.get_meta(key) or EPOCH


def _set_cursor(key: str, value: str, dry_run: bool) -> None:
    if not dry_run:
        learning_db.set_meta(key, value)


# ---------------------------------------------------------------------------
# Pattern extractors
# ---------------------------------------------------------------------------

def extract_category_preferences(
    outcomes: list[dict], dry_run: bool = False
) -> list[str]:
    """
    Group outcomes by suggestion_category.
    If ratio accepted/(accepted+skipped) >= MIN_SIGNALS signals → create/update skill.
    Returns list of actions taken (or would take).
    """
    by_category: dict[str, dict[str, int]] = defaultdict(lambda: {"accepted": 0, "skipped": 0, "total": 0})

    for o in outcomes:
        cat = o.get("suggestion_category") or "unknown"
        otype = o.get("outcome_type", "")
        by_category[cat]["total"] += 1
        if otype in ("accepted", "clicked", "bookmarked"):
            by_category[cat]["accepted"] += 1
        elif otype == "skipped":
            by_category[cat]["skipped"] += 1

    actions = []
    for cat, counts in by_category.items():
        total_signals = counts["accepted"] + counts["skipped"]
        if total_signals < MIN_SIGNALS:
            continue
        ratio = counts["accepted"] / total_signals
        skill_name = f"prefers_{cat.lower().replace(' ', '_')}"
        action = f"skill: {skill_name} confidence={ratio:.2f} signals={total_signals}"
        actions.append(action)
        if not dry_run:
            learning_db.create_skill(
                skill_name=skill_name,
                skill_category="preference",
                confidence=round(ratio, 3),
                signal_strength=total_signals,
                skill_data={"category": cat, "accepted": counts["accepted"], "skipped": counts["skipped"]},
            )

    return actions


def extract_cadence_drift(
    events: list[dict], outcomes: list[dict], dry_run: bool = False
) -> list[str]:
    """
    If most recent 10 suggestion outcomes are accepted and cadence > 30 → shorten cadence.
    """
    # Get suggestion events with cadence metadata
    suggestion_events = {
        e["id"]: e for e in events
        if e["event_type"] == "suggestion" and "cadence_minutes" in e.get("metadata", {})
    }

    # Match outcomes to suggestion events
    matched = []
    for o in outcomes:
        eid = o.get("event_id")
        if eid and eid in suggestion_events:
            matched.append({
                "outcome_type": o["outcome_type"],
                "cadence_minutes": suggestion_events[eid]["metadata"]["cadence_minutes"],
            })

    if len(matched) < 10:
        return []

    recent = matched[-10:]
    accepted_count = sum(1 for m in recent if m["outcome_type"] in ("accepted", "clicked", "bookmarked"))
    avg_cadence = sum(m["cadence_minutes"] for m in recent) / len(recent)

    actions = []
    if accepted_count >= 8 and avg_cadence > 30:
        new_cadence = max(30, int(avg_cadence * 0.75))
        action = f"pref: explore_cadence_minutes → {new_cadence} (was ~{int(avg_cadence)})"
        actions.append(action)
        if not dry_run:
            learning_db.set_preference(
                "explore_cadence_minutes",
                new_cadence,
                source="learned",
                confidence=0.7,
            )

    return actions


def extract_command_patterns(
    events: list[dict], dry_run: bool = False
) -> list[str]:
    """
    Count command_usage events by command name.
    Create skill for commands used frequently (≥ MIN_SIGNALS times).
    """
    cmd_counts: dict[str, int] = defaultdict(int)

    for e in events:
        if e["event_type"] == "command_usage":
            cmd = e.get("metadata", {}).get("command", "unknown")
            cmd_counts[cmd] += 1

    actions = []
    for cmd, count in cmd_counts.items():
        if count < MIN_SIGNALS:
            continue
        skill_name = f"frequent_{cmd.strip('/').lower()}_user"
        confidence = min(count / 10.0, 1.0)
        action = f"skill: {skill_name} confidence={confidence:.2f} signals={count}"
        actions.append(action)
        if not dry_run:
            learning_db.create_skill(
                skill_name=skill_name,
                skill_category="preference",
                confidence=round(confidence, 3),
                signal_strength=count,
                skill_data={"command": cmd, "usage_count": count},
            )

    return actions


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_learner(dry_run: bool = False, force: bool = False) -> None:
    now = datetime.now(timezone.utc).isoformat()
    mode = "[DRY RUN] " if dry_run else ""
    print(f"{mode}🧠 PersGraph Learning Worker — {now}")

    # Reset cursors if force
    if force and not dry_run:
        learning_db.set_meta(EVENT_CURSOR_KEY, EPOCH)
        learning_db.set_meta(OUTCOME_CURSOR_KEY, EPOCH)
        print("  [force] Cursors reset to epoch")
    elif force and dry_run:
        print("  [force+dry-run] Would reset cursors to epoch")

    event_cursor = EPOCH if force else _get_cursor(EVENT_CURSOR_KEY)
    outcome_cursor = EPOCH if force else _get_cursor(OUTCOME_CURSOR_KEY)

    print(f"  Event cursor:   {event_cursor}")
    print(f"  Outcome cursor: {outcome_cursor}")

    # Fetch new records
    events = learning_db.get_events_since(event_cursor)
    outcomes = learning_db.get_outcomes_since(outcome_cursor)

    print(f"  New events:   {len(events)}")
    print(f"  New outcomes: {len(outcomes)}")

    if not events and not outcomes:
        print("  Nothing new to process. Exiting.")
        if not dry_run:
            learning_db.set_meta(LAST_RUN_KEY, now)
        return

    all_actions = []

    # Run extractors
    actions = extract_category_preferences(outcomes, dry_run=dry_run)
    if actions:
        print(f"\n  📊 Category preferences ({len(actions)}):")
        for a in actions:
            print(f"    → {a}")
    all_actions.extend(actions)

    actions = extract_cadence_drift(events, outcomes, dry_run=dry_run)
    if actions:
        print(f"\n  ⏱ Cadence drift ({len(actions)}):")
        for a in actions:
            print(f"    → {a}")
    all_actions.extend(actions)

    actions = extract_command_patterns(events, dry_run=dry_run)
    if actions:
        print(f"\n  💬 Command patterns ({len(actions)}):")
        for a in actions:
            print(f"    → {a}")
    all_actions.extend(actions)

    if not all_actions:
        print("\n  No patterns extracted (insufficient signals).")

    # Advance cursors
    if events:
        new_event_cursor = events[-1]["timestamp_utc"]
        _set_cursor(EVENT_CURSOR_KEY, new_event_cursor, dry_run)
        if dry_run:
            print(f"\n  [dry-run] Would set event cursor → {new_event_cursor}")

    if outcomes:
        new_outcome_cursor = outcomes[-1]["timestamp_utc"]
        _set_cursor(OUTCOME_CURSOR_KEY, new_outcome_cursor, dry_run)
        if dry_run:
            print(f"  [dry-run] Would set outcome cursor → {new_outcome_cursor}")

    if not dry_run:
        learning_db.set_meta(LAST_RUN_KEY, now)

    print(f"\n  ✅ Done. {len(all_actions)} pattern(s) {'would be ' if dry_run else ''}written.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PersGraph Learning Worker")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no writes")
    parser.add_argument("--force", action="store_true", help="Reprocess all records from beginning")
    args = parser.parse_args()
    run_learner(dry_run=args.dry_run, force=args.force)
