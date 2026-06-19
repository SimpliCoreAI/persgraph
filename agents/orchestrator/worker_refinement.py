"""
Worker Refinement — Signal Consumer for Router & Worker Registry Improvements

Consumes learning signals from the learning layer to refine:
  1. Worker selection confidence (via routing signals)
  2. Approval/rejection likelihood (via approval signals)
  3. Worker success rates (via outcome signals)
  4. Command routing patterns (cross-signal analysis)

This module bridges the learning_signals module and the worker_registry,
enabling the orchestrator to make progressively better routing decisions
based on collected signals.

Typical usage (called by learning worker or on-demand):
    from agents.orchestrator.worker_refinement import (
        suggest_worker_adjustments,
        apply_worker_confidence_scores,
    )

    suggestions = suggest_worker_adjustments()
    # Returns list of tuples: (worker_type, command, reason, confidence_adjustment)

    # Optionally apply confidence boosts based on signals
    apply_worker_confidence_scores()
"""

from __future__ import annotations

from typing import Optional
from agents.orchestrator.learning_signals import (
    compute_routing_confidence,
    compute_approval_likelihood,
    compute_worker_success_rate,
    get_routing_signals,
    get_approval_signals,
    get_outcome_signals,
    get_signal_stats,
)
from agents.orchestrator.worker_registry import WorkerType, WORKER_CAPABILITIES


def suggest_worker_adjustments(
    min_signals: int = 3,
    confidence_threshold: float = 0.75,
) -> list[dict]:
    """
    Generate suggestions for worker routing adjustments based on signals.

    Analyzes:
      - Routing signals: which workers are assigned to which commands
      - Outcome signals: which workers succeed/fail most often
      - Approval signals: which decisions are made for each worker/command

    Args:
        min_signals: Minimum signal count before suggesting adjustment
        confidence_threshold: Confidence threshold for suggestions

    Returns:
        List of adjustment suggestions:
        [
            {
                "worker_type": "inbox_triage",
                "command": "/note",
                "reason": "High success rate (95%) based on 12 signals",
                "confidence_adjustment": +0.05,
                "current_confidence": 1.0,
                "new_confidence": 1.0,
                "signal_count": 12,
            },
            ...
        ]
    """
    suggestions = []
    stats = get_signal_stats()

    # Need at least min_signals total to make suggestions
    if stats["total_signals"] < min_signals:
        return []

    # Analyze each worker/command combination
    for worker_type_enum in [wt for wt in WorkerType]:
        worker_type = worker_type_enum.value

        # Get relevant signals for this worker
        routing_signals = get_routing_signals(worker_type=worker_type, limit=1000)
        outcome_signals = get_outcome_signals(worker_type=worker_type, limit=1000)

        if not routing_signals:
            continue  # No signals yet for this worker

        # Compute current confidence and new suggestion
        current_conf = compute_routing_confidence(worker_type, "*")  # Overall
        success_rate = compute_worker_success_rate(worker_type)

        # Suggest adjustment based on success rate
        adjustment = 0.0
        if success_rate >= 0.95:
            adjustment = +0.05  # Boost confidence
        elif success_rate >= 0.85:
            adjustment = +0.02
        elif success_rate < 0.60:
            adjustment = -0.10  # Reduce confidence
        elif success_rate < 0.75:
            adjustment = -0.05

        if abs(adjustment) > 0.0:
            new_conf = min(1.0, max(0.0, current_conf + adjustment))
            suggestions.append({
                "worker_type": worker_type,
                "command": "*",  # Overall adjustment
                "reason": f"Success rate {success_rate:.1%} from {len(outcome_signals)} outcomes",
                "confidence_adjustment": adjustment,
                "current_confidence": current_conf,
                "new_confidence": new_conf,
                "signal_count": len(outcome_signals),
            })

        # Per-command adjustments
        cmd_set = set(s.get("command") for s in routing_signals)
        for command in cmd_set:
            if not command:
                continue

            cmd_routing = [s for s in routing_signals if s.get("command") == command]
            cmd_outcomes = [s for s in outcome_signals if s.get("command") == command]

            if len(cmd_outcomes) < min_signals:
                continue  # Not enough signals

            cmd_success = (
                sum(1 for o in cmd_outcomes if o.get("success")) / len(cmd_outcomes)
                if cmd_outcomes else 1.0
            )

            cmd_conf = compute_routing_confidence(worker_type, command)
            cmd_adjustment = 0.0

            if cmd_success >= 0.95:
                cmd_adjustment = +0.05
            elif cmd_success >= 0.85:
                cmd_adjustment = +0.02
            elif cmd_success < 0.60:
                cmd_adjustment = -0.10
            elif cmd_success < 0.75:
                cmd_adjustment = -0.05

            if abs(cmd_adjustment) > 0.01:
                new_conf = min(1.0, max(0.0, cmd_conf + cmd_adjustment))
                suggestions.append({
                    "worker_type": worker_type,
                    "command": command,
                    "reason": f"Command success rate {cmd_success:.1%} from {len(cmd_outcomes)} outcomes",
                    "confidence_adjustment": cmd_adjustment,
                    "current_confidence": cmd_conf,
                    "new_confidence": new_conf,
                    "signal_count": len(cmd_outcomes),
                })

    return suggestions


def suggest_approval_refinements(
    min_signals: int = 5,
) -> list[dict]:
    """
    Generate suggestions for approval gate refinements.

    Analyzes approval signals to suggest:
    - Commands that should always be auto-approved (high approval rate)
    - Commands that should always be flagged (high rejection rate)

    Args:
        min_signals: Minimum approval decisions per command

    Returns:
        List of refinement suggestions:
        [
            {
                "command": "/note",
                "suggestion": "always_approve",
                "approval_rate": 0.98,
                "signal_count": 50,
                "reason": "98% approval rate over 50 decisions",
            },
            ...
        ]
    """
    suggestions = []
    stats = get_signal_stats()

    if stats["approval_signals"] < min_signals:
        return []

    all_approvals = get_approval_signals(limit=10000)

    # Group by command
    by_command = {}
    for signal in all_approvals:
        cmd = signal.get("command", "unknown")
        if cmd not in by_command:
            by_command[cmd] = []
        by_command[cmd].append(signal)

    # Analyze each command
    for command, signals in by_command.items():
        if len(signals) < min_signals:
            continue  # Not enough decisions

        approvals = sum(1 for s in signals if s.get("decision") == "approved")
        rejections = sum(1 for s in signals if s.get("decision") == "rejected")
        skipped = sum(1 for s in signals if s.get("decision") == "skipped")

        total = approvals + rejections + skipped
        approval_rate = approvals / total if total > 0 else 0.5

        # Make suggestions
        if approval_rate >= 0.98:
            suggestions.append({
                "command": command,
                "suggestion": "always_approve",
                "approval_rate": approval_rate,
                "signal_count": len(signals),
                "reason": f"{approval_rate:.1%} approval rate (rarely rejected)",
            })
        elif approval_rate <= 0.02:
            suggestions.append({
                "command": command,
                "suggestion": "always_reject",
                "approval_rate": approval_rate,
                "signal_count": len(signals),
                "reason": f"{approval_rate:.1%} approval rate (almost always rejected)",
            })

    return suggestions


def get_learned_preferences() -> dict:
    """
    Extract learned user preferences/patterns from signals.

    Combines:
      - Category preferences (from learning_db skills)
      - Command frequency (from routing signals)
      - Success patterns (from outcome signals)

    Returns:
        Dictionary with learned preferences:
        {
            "preferred_commands": [("/note", 25), ("/ask", 15), ...],
            "problematic_workers": [("travel_scout", 0.4), ...],
            "high_confidence_routes": [("inbox_triage", "/note", 0.98), ...],
        }
    """
    routing = get_routing_signals(limit=10000)
    outcomes = get_outcome_signals(limit=10000)

    # Command frequency
    cmd_counts = {}
    for signal in routing:
        cmd = signal.get("command", "unknown")
        cmd_counts[cmd] = cmd_counts.get(cmd, 0) + 1

    preferred_commands = sorted(cmd_counts.items(), key=lambda x: x[1], reverse=True)

    # Worker success rates
    worker_success = {}
    for worker in [wt.value for wt in WorkerType]:
        success = compute_worker_success_rate(worker)
        if success < 0.95:  # Only flag problematic ones
            worker_success[worker] = success

    problematic_workers = sorted(worker_success.items(), key=lambda x: x[1])

    # High confidence routes
    high_conf_routes = []
    for signal in routing:
        if signal.get("confidence", 1.0) >= 0.95:
            high_conf_routes.append((
                signal.get("worker_type"),
                signal.get("command"),
                signal.get("confidence", 1.0),
            ))

    return {
        "preferred_commands": preferred_commands[:10],
        "problematic_workers": problematic_workers,
        "high_confidence_routes": high_conf_routes[:10],
        "total_routed_commands": len(routing),
        "total_completed_commands": len([o for o in outcomes if o.get("success")]),
    }


def export_refinement_report(file_path: str) -> None:
    """
    Export a full refinement report (JSON) for analysis.

    Args:
        file_path: Path to write report to
    """
    import json
    from pathlib import Path

    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    adjustments = suggest_worker_adjustments()
    approvals = suggest_approval_refinements()
    prefs = get_learned_preferences()
    stats = get_signal_stats()

    report = {
        "timestamp": __import__('datetime').datetime.now().isoformat(),
        "signal_stats": stats,
        "worker_adjustments": adjustments,
        "approval_refinements": approvals,
        "learned_preferences": prefs,
    }

    with open(file_path, "w") as f:
        json.dump(report, f, indent=2)


def describe_refinement_state() -> dict:
    """
    Return a snapshot of the current refinement state (for debugging).

    Returns:
        Dictionary with current state and suggestions
    """
    return {
        "signal_stats": get_signal_stats(),
        "worker_adjustments": suggest_worker_adjustments(),
        "approval_refinements": suggest_approval_refinements(),
        "learned_preferences": get_learned_preferences(),
    }
