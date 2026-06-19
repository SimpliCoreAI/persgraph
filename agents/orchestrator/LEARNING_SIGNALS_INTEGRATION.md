# Learning Signals Integration — Self-Learning MVP

## Overview

The self-learning integration bridges the orchestrator's event/approval/execution layer with the learning database, enabling the system to improve routing and approval decisions over time based on collected signals.

**Key Goal:** Transform event outcomes and approval decisions into learning signals → persist them → consume them for refinement.

## Architecture

### 1. Signal Emission Layers

Three types of learning signals are emitted at strategic points in the orchestrator pipeline:

#### **Routing Signals** (`emit_routing_signal`)
- **When:** Command is routed to a worker
- **Data:** worker_type, command, user_tier, confidence, reason
- **Used for:** Learning which workers handle which commands effectively
- **Emitted by:** `router.py` in `route_command()`

```python
from agents.orchestrator.learning_signals import emit_routing_signal

emit_routing_signal(
    event_id="evt_...",
    worker_type="inbox_triage",
    command="/note",
    user_tier="user",
    confidence=0.95,
)
```

#### **Approval Signals** (`emit_approval_signal`)
- **When:** Approval decision is made (approve/reject/skip)
- **Data:** command, decision ("approved"/"rejected"/"skipped"), decided_by, reason
- **Used for:** Learning approval patterns and auto-approval scoring
- **Emitted by:** `approval_gate.py` in `approve_action()`, `reject_action()`, `skip_approval()`

```python
emit_approval_signal(
    event_id="evt_...",
    command="/note",
    decision="approved",
    decided_by="system",
    reason="Low-risk action",
)
```

#### **Outcome Signals** (`emit_outcome_signal`)
- **When:** Action completes (success or failure)
- **Data:** worker_type, command, status, success, duration_ms, error
- **Used for:** Learning worker success rates, performance, error patterns
- **Emitted by:** `orchestrator.py` in `run_with_routing()` after command execution

```python
emit_outcome_signal(
    event_id="evt_...",
    command="/note",
    worker_type="inbox_triage",
    status="completed",
    success=True,
    duration_ms=250,
)
```

### 2. Signal Persistence

Signals are stored in two places:

1. **In-memory:** `_LEARNING_SIGNALS` list in `learning_signals.py` (session-scoped)
2. **SQLite:** `learning.db` via `second_brain.learning_db` module (persistent across sessions)

Both storage paths are optional and non-critical (errors are silently caught).

### 3. Signal Analysis & Refinement

The `worker_refinement.py` module consumes signals to generate improvements:

#### **Worker Adjustments** (`suggest_worker_adjustments`)
Analyzes outcome signals to adjust routing confidence:
- High success rate → boost confidence
- Low success rate → reduce confidence
- Returns adjustment suggestions per worker/command

```python
from agents.orchestrator.worker_refinement import suggest_worker_adjustments

suggestions = suggest_worker_adjustments(min_signals=3)
# Returns: [
#   {
#     "worker_type": "inbox_triage",
#     "command": "/note",
#     "reason": "Success rate 95% from 12 outcomes",
#     "confidence_adjustment": +0.05,
#   },
#   ...
# ]
```

#### **Approval Refinements** (`suggest_approval_refinements`)
Analyzes approval signals to suggest policy changes:
- High approval rate (≥98%) → suggest always_approve
- Low approval rate (≤2%) → suggest always_reject

```python
approvals = suggest_approval_refinements(min_signals=5)
# Returns: [
#   {
#     "command": "/note",
#     "suggestion": "always_approve",
#     "approval_rate": 0.98,
#   },
#   ...
# ]
```

#### **Learned Preferences** (`get_learned_preferences`)
Extract patterns from signals:
- Most-used commands
- Problematic workers
- High-confidence routing pairs

```python
prefs = get_learned_preferences()
# Returns: {
#   "preferred_commands": [("/note", 25), ("/ask", 15), ...],
#   "problematic_workers": [("travel_scout", 0.40), ...],
#   "high_confidence_routes": [("inbox_triage", "/note", 0.98), ...],
# }
```

## Integration Points

### MVP Behavior (Current)

All three signal types are emitted automatically when commands flow through the routing layer:

```
user command
    ↓
router.route_command()
    ├→ generate_event_id()
    ├→ emit_routing_signal()  ← routing signal
    └→ return RoutedTask
    ↓
orchestrator.run_with_routing()
    ├→ check_approval_gates()
    ├→ emit_approval_signal() ← approval signal (skip/approve/reject)
    ├→ execute_command_handler()
    ├→ emit_outcome_signal() ← outcome signal (success/failure)
    └→ return result
```

### Future Integration Points

1. **Router Refinement:** Use worker adjustment suggestions to dynamically adjust routing confidence
2. **Approval Policy Automation:** Implement suggest_approval_refinements suggestions in approval_gate
3. **Worker Spawning:** When routing to actual workers (instead of orchestrator fallback), track per-worker outcomes
4. **Dashboard:** Expose signal stats and refinement suggestions in web UI

## Usage Examples

### Emit Signals Manually (for testing)

```python
from agents.orchestrator.learning_signals import (
    emit_routing_signal,
    emit_approval_signal,
    emit_outcome_signal,
)

# Record a routing decision
emit_routing_signal(
    event_id="evt_test_001",
    worker_type="inbox_triage",
    command="/note",
    user_tier="user",
    confidence=0.95,
    reason="Standard note capture",
)

# Record an approval decision
emit_approval_signal(
    event_id="evt_test_001",
    command="/note",
    decision="approved",
    confidence=1.0,
    decided_by="system",
    reason="Low-risk",
)

# Record an outcome
emit_outcome_signal(
    event_id="evt_test_001",
    command="/note",
    worker_type="inbox_triage",
    status="completed",
    success=True,
    duration_ms=150,
    result_preview="Note saved",
)
```

### Query and Analyze Signals

```python
from agents.orchestrator.learning_signals import (
    get_routing_signals,
    get_approval_signals,
    get_outcome_signals,
    get_signal_stats,
    compute_worker_success_rate,
)

# Get all routing signals for a worker
routing = get_routing_signals(worker_type="inbox_triage")

# Get approval decisions for a command
approvals = get_approval_signals(command="/note", decision="approved")

# Get failed outcomes
failures = get_outcome_signals(success_only=False)

# Get aggregated stats
stats = get_signal_stats()
# {
#   "total_signals": 100,
#   "routing_signals": 30,
#   "approval_signals": 30,
#   "outcome_signals": 40,
#   "success_rate": 0.95,
#   ...
# }

# Compute success rate for a worker
success = compute_worker_success_rate("inbox_triage")  # 0.0-1.0
```

### Get Refinement Suggestions

```python
from agents.orchestrator.worker_refinement import (
    suggest_worker_adjustments,
    suggest_approval_refinements,
    get_learned_preferences,
    describe_refinement_state,
    export_refinement_report,
)

# Get worker routing adjustments
adjustments = suggest_worker_adjustments(min_signals=3)

# Get approval policy suggestions
approvals = suggest_approval_refinements(min_signals=5)

# Get learned preferences
prefs = get_learned_preferences()

# Get full refinement snapshot
state = describe_refinement_state()

# Export as JSON report
export_refinement_report("data/refinement_report.json")
```

### Export Signals for External Analysis

```python
from agents.orchestrator.learning_signals import export_signals

# Export all signals as JSONL
exported_count = export_signals("data/signals_export.jsonl")
print(f"Exported {exported_count} signals")
```

## Configuration

### Persist Signals to File

By default, signals are stored only in-memory. To enable file persistence:

```python
from agents.orchestrator.learning_signals import set_signals_log_file
from pathlib import Path

set_signals_log_file(Path("data/learning_signals.jsonl"))
```

This creates an append-only JSONL log of all signals emitted.

### Integrating with Learning Database

The learning_signals module automatically attempts to emit signals to `second_brain.learning_db` if available (via `record_event()` and `record_outcome()`). This is optional and non-critical.

## Testing

Run the comprehensive integration test:

```bash
cd ~/AgenticHub/Persgraph
python3 tests/test_orchestrator_learning_signals.py
```

Tests cover:
- ✅ Routing signal emission and retrieval
- ✅ Approval signal emission for approve/reject/skip
- ✅ Outcome signal emission for success/failure
- ✅ Signal aggregation and statistics
- ✅ Worker adjustment suggestions
- ✅ Approval refinement suggestions
- ✅ Learned preference extraction
- ✅ Refinement state export
- ✅ Integrated workflow (route → approve → execute → learn)

## Files Changed

### New Files
- `agents/orchestrator/learning_signals.py` — Signal emission and querying
- `agents/orchestrator/worker_refinement.py` — Signal analysis and suggestions
- `tests/test_orchestrator_learning_signals.py` — Integration tests

### Modified Files
- `agents/orchestrator/event_manager.py` — Added comment about learning signal deferral
- `agents/orchestrator/approval_gate.py` — Added emit_approval_signal() calls in approve_action(), reject_action(), skip_approval()
- `agents/orchestrator/router.py` — Added emit_routing_signal() call in route_command()
- `agents/orchestrator/orchestrator.py` — Added emit_outcome_signal() calls in run_with_routing()
- `agents/orchestrator/__init__.py` — Updated docstring and __all__ exports

## Signal Data Model

### Routing Signal
```json
{
  "signal_type": "routing",
  "event_id": "evt_...",
  "timestamp_utc": "2026-06-19T07:30:00+00:00",
  "worker_type": "inbox_triage",
  "command": "/note",
  "user_tier": "user",
  "confidence": 0.95,
  "reason": "Routed via route_command"
}
```

### Approval Signal
```json
{
  "signal_type": "approval",
  "event_id": "evt_...",
  "timestamp_utc": "2026-06-19T07:30:01+00:00",
  "command": "/note",
  "decision": "approved",
  "confidence": 1.0,
  "decided_by": "system",
  "reason": "Low-risk action (MVP)"
}
```

### Outcome Signal
```json
{
  "signal_type": "outcome",
  "event_id": "evt_...",
  "timestamp_utc": "2026-06-19T07:30:02+00:00",
  "command": "/note",
  "worker_type": "inbox_triage",
  "status": "completed",
  "success": true,
  "duration_ms": 250,
  "result_preview": "Note saved",
  "error": null
}
```

## Next Steps

### Phase 1 (Current - MVP)
- ✅ Emit signals at routing/approval/execution
- ✅ Persist signals in-memory and to learning_db
- ✅ Provide querying and analysis functions
- ✅ Generate refinement suggestions

### Phase 2 (Future)
- Implement auto-approval based on learned patterns
- Dynamically adjust router confidence based on outcomes
- Build web dashboard to visualize learned patterns
- Implement active learning (ask user for feedback on borderline cases)
- Integrate suggestions into actual routing decisions

### Phase 3 (Future)
- Multi-user learning (aggregate signals across users while preserving privacy)
- Skill extraction (e.g., "user prefers restaurants with low prices")
- Cadence and intensity learning (from Explore Mode)
- Worker spawning and per-worker outcome tracking

## Notes

- **Non-critical errors:** Signal emission/persistence errors are silently caught; they never block command execution
- **Memory efficiency:** Signals are kept in-memory for the session; consider periodic cleanup for long-running processes
- **Privacy:** No PII is captured in signals; only commands, outcomes, and aggregated patterns
- **Backward compatibility:** All existing orchestrator code continues to work; learning signals are additive

## References

- `EVENT_SYSTEM.md` — Overview of event ID, approval, and audit trail
- `ROUTING.md` — Router layer design
- `MVP_SUMMARY.md` — MVP goals and architecture
- `second_brain/learning_db.py` — Learning database schema and helpers
