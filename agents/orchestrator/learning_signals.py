"""
Learning Signals Integration — Bridge between Orchestrator Events and Learning Layer

Converts orchestrator events (routing, approval, execution) and outcomes into
learning signals that persist in learning_db for pattern extraction and
decision refinement.

Key responsibilities:
  1. Transform event outcomes into learning signals (events/outcomes)
  2. Map approval decisions to confidence/preference signals
  3. Track decision patterns for worker/router refinement
  4. Expose signals via consumer interface for worker registry feedback

Usage:
    from agents.orchestrator.learning_signals import (
        emit_routing_signal, emit_approval_signal, emit_outcome_signal
    )

    # When command is routed:
    emit_routing_signal(event_id, worker_type, confidence=0.95)

    # When approval is granted/denied:
    emit_approval_signal(event_id, decision="approved", confidence=0.8)

    # When action completes:
    emit_outcome_signal(event_id, status="completed", success=True)
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional
from pathlib import Path

UTC = ZoneInfo("UTC")

# In-memory learning signal store
_LEARNING_SIGNALS: list[dict] = []

# Optional file path for persistence (append-only)
_SIGNALS_LOG_FILE: Optional[Path] = None


def set_signals_log_file(file_path: Path | str) -> None:
    """
    Set the file path for learning signals persistence.

    Args:
        file_path: Path to append-only learning signals log
    """
    global _SIGNALS_LOG_FILE
    _SIGNALS_LOG_FILE = Path(file_path)


def emit_routing_signal(
    event_id: str,
    worker_type: Optional[str],
    command: str,
    user_tier: str,
    confidence: float = 1.0,
    reason: str = "",
) -> None:
    """
    Emit a routing signal when a command is routed to a worker.

    Used to learn: which workers are assigned to which commands/user_tiers,
    and build confidence in routing decisions.

    Args:
        event_id: The event ID of the routed action
        worker_type: Worker assigned (or None for orchestrator bypass)
        command: The command being routed
        user_tier: User tier (guest, kid, user, admin)
        confidence: Confidence in routing (0.0-1.0)
        reason: Optional explanation
    """
    signal = {
        "signal_type": "routing",
        "event_id": event_id,
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "worker_type": worker_type,
        "command": command,
        "user_tier": user_tier,
        "confidence": confidence,
        "reason": reason,
    }

    _append_signal(signal)

    # Try to emit to learning_db
    try:
        from second_brain import learning_db
        learning_db.record_event(
            event_type="command_routing",
            metadata={
                "event_id": event_id,
                "worker_type": worker_type,
                "command": command,
                "user_tier": user_tier,
                "confidence": confidence,
                "reason": reason,
            }
        )
    except Exception:
        pass  # Learning layer not critical


def emit_approval_signal(
    event_id: str,
    command: str,
    decision: str,  # "approved", "rejected", "skipped"
    confidence: float = 1.0,
    decided_by: Optional[str] = None,
    reason: Optional[str] = None,
) -> None:
    """
    Emit an approval signal when an approval decision is made.

    Used to learn: which actions get approved/rejected, and build models
    for automatic approval scoring.

    Args:
        event_id: The event ID
        command: The command being approved/rejected
        decision: "approved", "rejected", or "skipped"
        confidence: Confidence in decision (0.0-1.0)
        decided_by: Who made the decision (username or "system")
        reason: Optional explanation
    """
    signal = {
        "signal_type": "approval",
        "event_id": event_id,
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "command": command,
        "decision": decision,
        "confidence": confidence,
        "decided_by": decided_by or "system",
        "reason": reason,
    }

    _append_signal(signal)

    # Try to emit to learning_db
    try:
        from second_brain import learning_db
        learning_db.record_event(
            event_type="approval_decision",
            metadata={
                "event_id": event_id,
                "command": command,
                "decision": decision,
                "confidence": confidence,
                "decided_by": decided_by or "system",
                "reason": reason,
            }
        )
    except Exception:
        pass  # Learning layer not critical


def emit_outcome_signal(
    event_id: str,
    command: str,
    worker_type: Optional[str],
    status: str,  # "completed", "failed", "cancelled", etc.
    success: bool,
    duration_ms: int = 0,
    result_preview: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    """
    Emit an outcome signal when an action completes (success or failure).

    Used to learn: execution success rates, performance characteristics,
    and error patterns for each worker/command combination.

    Args:
        event_id: The event ID
        command: The command executed
        worker_type: Worker that handled it
        status: Outcome status ("completed", "failed", "timeout", "cancelled")
        success: True if successful
        duration_ms: Execution time
        result_preview: Short preview of result (first 100 chars)
        error: Error message if failed
    """
    signal = {
        "signal_type": "outcome",
        "event_id": event_id,
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "command": command,
        "worker_type": worker_type,
        "status": status,
        "success": success,
        "duration_ms": duration_ms,
        "result_preview": result_preview,
        "error": error,
    }

    _append_signal(signal)

    # Try to emit to learning_db
    try:
        from second_brain import learning_db
        learning_db.record_outcome(
            event_id=event_id,
            outcome_type="completed" if success else "failed",
            suggestion_category="command_execution",
            engagement_seconds=max(1, duration_ms // 1000),
            feedback=result_preview,
            metadata={
                "command": command,
                "worker_type": worker_type,
                "status": status,
                "duration_ms": duration_ms,
                "error": error,
            }
        )
    except Exception:
        pass  # Learning layer not critical


def get_routing_signals(
    worker_type: Optional[str] = None,
    command: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """
    Query routing signals for analysis or debugging.

    Args:
        worker_type: Filter by worker type
        command: Filter by command
        limit: Maximum results

    Returns:
        List of routing signals
    """
    results = []
    for signal in _LEARNING_SIGNALS:
        if signal.get("signal_type") != "routing":
            continue
        if worker_type and signal.get("worker_type") != worker_type:
            continue
        if command and signal.get("command") != command:
            continue

        results.append(signal)
        if len(results) >= limit:
            break

    return results


def get_approval_signals(
    decision: Optional[str] = None,
    command: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """
    Query approval signals for analysis or debugging.

    Args:
        decision: Filter by decision ("approved", "rejected", "skipped")
        command: Filter by command
        limit: Maximum results

    Returns:
        List of approval signals
    """
    results = []
    for signal in _LEARNING_SIGNALS:
        if signal.get("signal_type") != "approval":
            continue
        if decision and signal.get("decision") != decision:
            continue
        if command and signal.get("command") != command:
            continue

        results.append(signal)
        if len(results) >= limit:
            break

    return results


def get_outcome_signals(
    status: Optional[str] = None,
    worker_type: Optional[str] = None,
    success_only: Optional[bool] = None,
    limit: int = 100,
) -> list[dict]:
    """
    Query outcome signals for analysis or debugging.

    Args:
        status: Filter by status
        worker_type: Filter by worker type
        success_only: If True, only successful outcomes; if False, only failures
        limit: Maximum results

    Returns:
        List of outcome signals
    """
    results = []
    for signal in _LEARNING_SIGNALS:
        if signal.get("signal_type") != "outcome":
            continue
        if status and signal.get("status") != status:
            continue
        if worker_type and signal.get("worker_type") != worker_type:
            continue
        if success_only is not None:
            if signal.get("success") != success_only:
                continue

        results.append(signal)
        if len(results) >= limit:
            break

    return results


def compute_routing_confidence(worker_type: Optional[str], command: str) -> float:
    """
    Compute average routing confidence for a worker/command pair.

    Used by router to adjust future routing decisions based on learned
    success patterns.

    Args:
        worker_type: Worker type
        command: Command string

    Returns:
        Average confidence (0.0-1.0)
    """
    signals = [
        s for s in _LEARNING_SIGNALS
        if (s.get("signal_type") == "routing"
            and s.get("worker_type") == worker_type
            and s.get("command") == command)
    ]

    if not signals:
        return 1.0  # Default confidence if no signals yet

    avg_conf = sum(s.get("confidence", 1.0) for s in signals) / len(signals)
    return min(avg_conf, 1.0)


def compute_approval_likelihood(command: str) -> float:
    """
    Compute likelihood that a command will be approved (if routed for approval).

    Used by router/approval gate to make approve/reject suggestions.

    Args:
        command: Command string

    Returns:
        Fraction of approvals to total decisions (0.0-1.0)
    """
    signals = [
        s for s in _LEARNING_SIGNALS
        if (s.get("signal_type") == "approval"
            and s.get("command") == command)
    ]

    if not signals:
        return 0.5  # Neutral if no signals yet

    approvals = sum(1 for s in signals if s.get("decision") == "approved")
    return approvals / len(signals) if signals else 0.5


def compute_worker_success_rate(worker_type: Optional[str], command: Optional[str] = None) -> float:
    """
    Compute success rate for a worker (optionally for a specific command).

    Used by orchestrator/router to make worker selection decisions.

    Args:
        worker_type: Worker type
        command: Optional command to filter by

    Returns:
        Fraction successful (0.0-1.0)
    """
    signals = [
        s for s in _LEARNING_SIGNALS
        if (s.get("signal_type") == "outcome"
            and s.get("worker_type") == worker_type)
    ]

    if command:
        signals = [s for s in signals if s.get("command") == command]

    if not signals:
        return 1.0  # Default (assume good) if no signals yet

    successes = sum(1 for s in signals if s.get("success"))
    return successes / len(signals) if signals else 1.0


def get_signal_stats() -> dict:
    """
    Get summary statistics about learning signals collected.

    Returns:
        Dictionary with signal counts and trends
    """
    routing_count = sum(1 for s in _LEARNING_SIGNALS if s.get("signal_type") == "routing")
    approval_count = sum(1 for s in _LEARNING_SIGNALS if s.get("signal_type") == "approval")
    outcome_count = sum(1 for s in _LEARNING_SIGNALS if s.get("signal_type") == "outcome")

    # Count approvals/rejections
    approvals = sum(
        1 for s in _LEARNING_SIGNALS
        if s.get("signal_type") == "approval" and s.get("decision") == "approved"
    )
    rejections = sum(
        1 for s in _LEARNING_SIGNALS
        if s.get("signal_type") == "approval" and s.get("decision") == "rejected"
    )

    # Count successful outcomes
    successes = sum(
        1 for s in _LEARNING_SIGNALS
        if s.get("signal_type") == "outcome" and s.get("success")
    )
    failures = sum(
        1 for s in _LEARNING_SIGNALS
        if s.get("signal_type") == "outcome" and not s.get("success")
    )

    return {
        "total_signals": len(_LEARNING_SIGNALS),
        "routing_signals": routing_count,
        "approval_signals": approval_count,
        "outcome_signals": outcome_count,
        "approvals": approvals,
        "rejections": rejections,
        "approvals_ratio": approvals / max(1, approvals + rejections),
        "successes": successes,
        "failures": failures,
        "success_rate": successes / max(1, successes + failures),
    }


def _append_signal(signal: dict) -> None:
    """
    Append a signal to the in-memory store and optionally to file.

    Args:
        signal: Dictionary signal to append
    """
    _LEARNING_SIGNALS.append(signal)

    # Persist to file if configured
    if _SIGNALS_LOG_FILE:
        try:
            import json
            _SIGNALS_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(_SIGNALS_LOG_FILE, "a") as f:
                f.write(json.dumps(signal) + "\n")
        except Exception as e:
            import sys
            print(f"[LEARNING SIGNALS ERROR] Failed to write signals log: {e}", file=sys.stderr)


def clear_signals() -> None:
    """
    Clear all in-memory learning signals (use for testing only).
    """
    _LEARNING_SIGNALS.clear()


def list_all_signals(limit: int = 1000) -> list[dict]:
    """
    List all signals with optional limit.

    Args:
        limit: Maximum to return

    Returns:
        List of signals
    """
    return _LEARNING_SIGNALS[-limit:] if _LEARNING_SIGNALS else []


def export_signals(file_path: Path | str) -> int:
    """
    Export all signals to a file (JSONL format).

    Args:
        file_path: Path to write to

    Returns:
        Number of signals exported
    """
    import json
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, "w") as f:
        for signal in _LEARNING_SIGNALS:
            f.write(json.dumps(signal) + "\n")

    return len(_LEARNING_SIGNALS)
