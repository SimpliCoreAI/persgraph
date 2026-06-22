# Event System, Approval Gates & Audit Trail — MVP Implementation

## Overview

This MVP increment adds event tracking, human-in-the-loop approval gates, and an append-only audit trail to PersGraph. Every routed action gets a unique event ID that ties together the request, approval decisions, execution, and outcomes.

## Components

### 1. Event Manager (`event_manager.py`)

**Purpose:** Generate and track unique event IDs for all significant actions.

**Key Functions:**
- `generate_event_id(worker_type, command, user_id)` → event_id (e.g., `evt_20260619072226_4408e4e8`)
- `get_event_context(event_id)` → dict with event metadata
- `update_event_status(event_id, status, ...)` → track state changes
- `correlate_feedback_event(original_id, feedback_id)` → link results back to actions
- `list_events(status=None, user_id=None)` → query events

**Event Lifecycle:**
```
created → pending_approval → approved/rejected → executed → completed
```

**Storage:** In-memory registry (future: persist to database)

**Example:**
```python
from agents.orchestrator.event_manager import generate_event_id, get_event_context

event_id = generate_event_id("inbox_triage", "/note", user_id="12345")
# event_id = "evt_20260619072226_4408e4e8"

ctx = get_event_context(event_id)
# {
#   "event_id": "evt_20260619072226_4408e4e8",
#   "worker_type": "inbox_triage",
#   "command": "/note",
#   "user_id": "12345",
#   "created_at": "2026-06-19T07:22:26+00:00",
#   "status": "created",
#   "approval_state": None,
# }
```

### 2. Approval Gate (`approval_gate.py`)

**Purpose:** Mark actions for human approval, track decisions, and enforce approval policies.

**Key Functions:**
- `mark_for_approval(event_id, command, args, reason, requires_human)` → queue for review
- `approve_action(event_id, approved_by, reason)` → authorize execution
- `reject_action(event_id, reason, rejected_by)` → deny execution
- `skip_approval(event_id, reason)` → bypass approval for low-risk actions
- `get_approval_status(event_id)` → check approval state
- `is_approved(event_id)` / `is_rejected(event_id)` → quick checks
- `list_pending_approvals(requires_human=True)` → get pending actions

**Approval States:**
```
pending → approved | rejected | skipped
```

**Storage:** In-memory registry (future: add Telegram/email notification hooks)

**Example:**
```python
from agents.orchestrator.approval_gate import (
    mark_for_approval, approve_action, is_approved
)

event_id = "evt_20260619072226_4408e4e8"

# Mark for approval
mark_for_approval(event_id, "/ingest", "https://example.com", reason="External URL")

# Admin approves
approve_action(event_id, approved_by="admin", reason="Safe domain")

# Proceed only if approved
if is_approved(event_id):
    execute_action(event_id)
```

### 3. Audit Logger (`audit_logger.py`)

**Purpose:** Append-only log of all actions, decisions, and outcomes for compliance/debugging.

**Key Functions:**
- `log_action(event_id, user_id, command, args, ...)` → log initial action
- `log_approval_request(event_id, command, reason, ...)` → log approval request
- `log_approval_decision(event_id, decision, decided_by, ...)` → log approval outcome
- `log_execution(event_id, worker_type, ...)` → log execution start
- `log_outcome(event_id, status, result, ...)` → log result (success/failure)
- `log_feedback(event_id, feedback_event_id, ...)` → log correlated feedback
- `read_audit_trail(event_id=None, user_id=None, ...)` → query trail
- `export_audit_trail(file_path)` → export to file
- `set_audit_log_file(file_path)` → enable file persistence

**Log Format:** JSON lines (one JSON object per line)

**Storage:** In-memory list + optional file persistence

**Example Entry:**
```json
{
  "event_type": "action_created",
  "event_id": "evt_20260619072226_4408e4e8",
  "timestamp": "2026-06-19T07:22:26.123456+00:00",
  "user_id": "12345",
  "command": "/note",
  "args": "buy groceries",
  "worker_type": "inbox_triage"
}
```

### 4. Enhanced Router (`router.py`)

**New Features:**
- `route_command()` now generates event_id and injects it into payload
- `route_command_with_gates()` applies approval gates
- Payload includes: `event_id`, `command`, `args`, `user_*`, `timestamp`
- RoutedTask now tracks: `requires_approval`, `approval_reason`
- Audit logging integrated into routing

**Example:**
```python
from agents.orchestrator.router import route_command_with_gates

user = {"id": "12345", "name": "alice", "tier": "user"}
routed = route_command_with_gates("/note buy groceries", user)

# routed.event_id = "evt_20260619072226_4408e4e8"
# routed.payload["event_id"] = event_id (available to worker)
# routed.requires_approval = False (MVP: all actions low-risk)
```

### 5. Enhanced Orchestrator (`orchestrator.py`)

**New Features:**
- `run_with_routing()` now logs execution start/finish
- Caught exceptions log failures to audit trail
- Approval gates checked before execution
- Event registry snapshot available via `get_event_registry_snapshot()`

**Example:**
```python
from agents.orchestrator.orchestrator import run_with_routing

result = run_with_routing("/note buy groceries", sender_id="12345")
# Audit trail automatically updated with:
# 1. action_created
# 2. (optionally) approval_requested, approval_granted
# 3. action_executed
# 4. action_completed (or action_failed)
```

### 6. Enhanced Worker Base (`worker_base.py`)

**New Features:**
- Workers can access `payload["event_id"]`
- Worker.run() logs outcomes automatically (if audit logger available)
- `attach_event_id(payload, event_id)` helper for manual updates

**Example:**
```python
class MyWorker(BaseWorker):
    def execute(self, payload: dict) -> str:
        event_id = payload.get("event_id")  # Available in payload
        # ... worker logic ...
        return result  # Outcome auto-logged with event_id
```

## Data Structures

### Event Context
```python
{
    "event_id": "evt_20260619072226_4408e4e8",
    "worker_type": "inbox_triage",
    "command": "/note",
    "user_id": "12345",
    "created_at": "2026-06-19T07:22:26+00:00",
    "status": "created|pending_approval|approved|rejected|executed|completed",
    "approval_state": None|"pending"|"approved"|"rejected"|"skipped",
    "result": None|"...",
    "feedback_event_id": None|"evt_...",
}
```

### Approval Status
```python
{
    "event_id": "evt_20260619072226_4408e4e8",
    "command": "/note",
    "args": "buy groceries",
    "reason": "User tier restricted",
    "requires_human": True,
    "state": "pending|approved|rejected|skipped",
    "requested_at": "2026-06-19T07:22:26+00:00",
    "decided_at": None|"2026-06-19T07:25:00+00:00",
    "decided_by": None|"admin|system",
    "decision_reason": None|"...",
}
```

### Audit Trail Entry
```python
{
    "event_type": "action_created|action_routed|approval_requested|approval_granted|approval_denied|action_executed|action_completed|action_failed|feedback_received",
    "event_id": "evt_20260619072226_4408e4e8",
    "timestamp": "2026-06-19T07:22:26.123456+00:00",
    # ... type-specific fields ...
}
```

## Integration Points

### For Command Handlers
No changes required. Existing handlers continue to work via direct `command_handler.run()`.

### For Workers
Workers automatically get `event_id` in payload:
```python
def execute(self, payload: dict) -> str:
    event_id = payload.get("event_id")  # Use for feedback correlation
    # ... worker logic ...
```

### For Orchestrator
Use new routing layer:
```python
from agents.orchestrator.router import route_command_with_gates
routed = route_command_with_gates(raw_input, user_context)
# Check routed.requires_approval before proceeding
```

### For Admin/Monitoring
Query approval status and audit trail:
```python
from agents.orchestrator.approval_gate import list_pending_approvals
from agents.orchestrator.audit_logger import read_audit_trail

pending = list_pending_approvals()
trail = read_audit_trail(user_id="12345")
```

## Backward Compatibility

✅ **All existing code continues to work:**
- `command_handler.run()` still works directly
- Workers don't require changes
- No breaking changes to existing APIs

✅ **New functionality is opt-in:**
- Use `route_command_with_gates()` to enable event tracking
- Use `run_with_routing()` to enable full orchestration + audit logging
- Leave as-is to keep existing behavior

## Future Enhancements

### Phase 2: Persistent Storage
- Store event/approval/audit data in SQLite
- Implement retention policies
- Add query/export endpoints

### Phase 3: Notification & Escalation
- Telegram notifications for pending approvals
- Email summaries of audit trail
- Escalation for long-pending decisions

### Phase 4: Policy Engine
- Define approval policies by command/user/tier
- Auto-approve low-risk actions
- Auto-reject high-risk from untrusted users
- Appeals/override workflow

### Phase 5: Analytics & Learning
- Track decision patterns (approval rate, decision time)
- Correlate with outcomes (was the decision correct?)
- Use feedback to improve policies

## Testing

**Run the test suite:**
```bash
cd ~/AgenticHub/Persgraph
.venv/bin/python -m pytest tests/test_event_system.py -v
```

**Test coverage:**
- ✅ Event ID generation and uniqueness
- ✅ Event context tracking and updates
- ✅ Approval gate lifecycle (pending → approved/rejected/skipped)
- ✅ Audit trail logging and querying
- ✅ Router integration with event IDs
- ✅ Feedback correlation
- ✅ Backward compatibility

All 18 tests pass.

## Usage Example: End-to-End Flow

```python
from agents.orchestrator.orchestrator import run_with_routing
from agents.orchestrator.approval_gate import list_pending_approvals
from agents.orchestrator.audit_logger import read_audit_trail

# 1. User sends command
result = run_with_routing("/note buy groceries", sender_id="12345")
# Action is logged with event_id

# 2. Admin checks pending approvals
pending = list_pending_approvals()
# (None in MVP, all actions auto-approved)

# 3. View audit trail
trail = read_audit_trail(user_id="12345")
# Shows: action_created, (approval flow), action_executed, action_completed

# 4. Query specific event
trail = read_audit_trail(event_id="evt_20260619072226_4408e4e8")
# Full lifecycle of the action
```

## Files Added/Modified

### Added
- `agents/orchestrator/event_manager.py` (200 lines, 4.7 KB)
- `agents/orchestrator/approval_gate.py` (280 lines, 7.1 KB)
- `agents/orchestrator/audit_logger.py` (360 lines, 8.4 KB)
- `tests/test_event_system.py` (400 lines, 11.6 KB)
- `agents/orchestrator/EVENT_SYSTEM.md` (this file)

### Modified
- `agents/orchestrator/router.py` (now includes event ID generation + audit logging)
- `agents/orchestrator/orchestrator.py` (now includes execution/outcome logging)
- `agents/orchestrator/worker_base.py` (now includes outcome logging + event_id attachment)

### No Changes Required
- `agents/orchestrator/command_handler.py`
- `agents/orchestrator/worker_registry.py`
- All existing workers and command handlers

## Deployment Notes

1. **Zero breaking changes** – Deploy immediately, no migration needed
2. **No new dependencies** – Uses only stdlib (json, datetime, enum, uuid)
3. **Memory footprint** – In-memory registries grow with event count; plan for persistence before large-scale use
4. **File persistence** – Optional via `set_audit_log_file()`; default is in-memory

## Questions?

Refer to the test suite (`tests/test_event_system.py`) for usage examples and integration patterns.
