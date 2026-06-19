# Changelog — Event System MVP Increment

## Version: Event System MVP (2026-06-19)

### Overview
Added event-id-based action tracking, human approval gates, and append-only audit trail to the PersGraph orchestrator.

### Files Added

#### Core Modules
- **`event_manager.py`** (173 lines)
  - Event ID generation with timestamp + UUID
  - Event context tracking and updates
  - Feedback loop correlation
  - Event registry (in-memory)
  
  Functions:
  - `generate_event_id(worker_type, command, user_id)` → str
  - `get_event_context(event_id)` → dict | None
  - `update_event_status(event_id, status, ...)` → bool
  - `correlate_feedback_event(original_id, feedback_id)` → bool
  - `list_events(status, user_id, limit)` → list[dict]
  - `clear_event_registry()` → None

- **`approval_gate.py`** (288 lines)
  - Human-in-the-loop approval workflow
  - Approval state machine (pending → approved/rejected/skipped)
  - Admin dashboard support (list pending approvals)
  - Approval registry (in-memory)
  
  Functions:
  - `mark_for_approval(event_id, command, args, reason, requires_human)` → bool
  - `approve_action(event_id, approved_by, reason)` → bool
  - `reject_action(event_id, reason, rejected_by)` → bool
  - `skip_approval(event_id, reason)` → bool
  - `get_approval_status(event_id)` → dict | None
  - `is_approved(event_id)` → bool
  - `is_rejected(event_id)` → bool
  - `list_pending_approvals(requires_human, limit)` → list[dict]
  - `clear_approval_registry()` → None

- **`audit_logger.py`** (331 lines)
  - Append-only action and outcome logging
  - Event types: action_created, approval_requested, approval_granted, approval_denied, action_executed, action_completed, action_failed, feedback_received
  - Queryable by event_id, user_id, event_type, date range
  - Optional file persistence (JSON lines)
  - Audit trail (in-memory + optional file)
  
  Functions:
  - `log_action(event_id, user_id, command, args, worker_type, metadata)` → None
  - `log_approval_request(event_id, command, reason, requested_by)` → None
  - `log_approval_decision(event_id, decision, decided_by, reason)` → None
  - `log_execution(event_id, worker_type, status)` → None
  - `log_outcome(event_id, status, result, worker_type, error)` → None
  - `log_feedback(event_id, feedback_event_id, feedback_data)` → None
  - `read_audit_trail(event_id, user_id, event_type, limit)` → list[dict]
  - `set_audit_log_file(file_path)` → None
  - `export_audit_trail(file_path)` → int
  - `clear_audit_trail()` → None
  - `get_audit_trail_size()` → int

#### Documentation
- **`EVENT_SYSTEM.md`** (354 lines)
  - Complete reference guide for the event system
  - Component descriptions and API docs
  - Data structures and examples
  - Integration points
  - Backward compatibility notes
  - Future enhancement roadmap

- **`MVP_SUMMARY.md`** (347 lines)
  - High-level overview of the MVP
  - What was built and why
  - Test results (18/18 unit tests, 5/5 smoke tests)
  - Usage examples
  - Architecture diagram
  - Known limitations and future phases

- **`CHANGELOG.md`** (this file)
  - Detailed list of changes

#### Tests
- **`test_event_system.py`** (338 lines)
  - 18 comprehensive unit tests
  - Coverage:
    - Event ID generation and uniqueness
    - Event context tracking and updates
    - Approval gate lifecycle
    - Audit trail logging and querying
    - Router integration with event IDs
    - Feedback correlation
  - All tests pass ✓

- **`smoke_test_event_system.py`** (223 lines)
  - 5 end-to-end integration tests
  - Coverage:
    - Basic event flow
    - Approval gates
    - Audit trail
    - Router integration
    - Full end-to-end workflow
  - All tests pass ✓

### Files Modified

#### `router.py` (+80 lines)
**Changes:**
- Added `event_id` field to `RoutedTask` NamedTuple
- Added `requires_approval` and `approval_reason` fields to `RoutedTask`
- `route_command()` now:
  - Generates event ID for every command
  - Injects event_id into payload
  - Logs action to audit trail
- New function: `route_command_with_gates()`
  - Wraps `route_command()` with approval gate logic
  - Currently skips approval for all actions (MVP)
  - Future: policy-based approval decisions
- `summarize_routing()` now includes event_id and requires_approval in summary

**Backward Compatibility:**
- Old `route_command()` API still works
- Existing code continues to function
- New fields in RoutedTask are opt-in to use

#### `orchestrator.py` (+50 lines)
**Changes:**
- `run_with_routing()` now:
  - Uses `route_command_with_gates()` instead of `route_command()`
  - Checks approval gates before execution
  - Logs execution start with `log_execution()`
  - Logs outcome (success or failure) with `log_outcome()`
  - Returns pause message if approval pending
- New function: `get_event_registry_snapshot()`
  - Returns snapshot of total events, pending approvals, recent events
  - Useful for monitoring/debugging
- Better error handling with audit trail logging

**Backward Compatibility:**
- Direct `command_handler.run()` still works
- `run_with_routing()` is opt-in

#### `worker_base.py` (+45 lines)
**Changes:**
- `run()` method now:
  - Automatically logs outcome (success) with `log_outcome()`
  - Automatically logs failures with error details
  - Preserves existing behavior (try-catch pattern)
- New helper method: `attach_event_id(payload, event_id)`
  - Allows workers to update event_id if needed
  - Utility for advanced worker implementations
- Optional audit logging (fails gracefully if not available)

**Backward Compatibility:**
- No breaking changes
- Existing workers work without modification
- New logging is automatic and transparent

### Data Structures

#### Event Context (from `event_manager.py`)
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

#### Approval Status (from `approval_gate.py`)
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

#### Audit Entry (from `audit_logger.py`)
```python
{
    "event_type": "action_created|approval_requested|approval_granted|...",
    "event_id": "evt_20260619072226_4408e4e8",
    "timestamp": "2026-06-19T07:22:26.123456+00:00",
    # ... type-specific fields ...
}
```

### Behavior Changes

#### Routing
- **Before:** `route_command()` returns RoutedTask with no event tracking
- **After:** `route_command()` generates event_id, injects into payload, logs action

#### Execution
- **Before:** Commands executed directly via `command_handler.run()`
- **After:** Can opt-in to `run_with_routing()` for full tracking + approval gates

#### Worker Outcomes
- **Before:** Worker results not tracked to original event
- **After:** Worker outcomes automatically logged with event_id (if audit logger available)

### API Changes

#### New Public APIs
- `agents.orchestrator.event_manager.generate_event_id()`
- `agents.orchestrator.event_manager.get_event_context()`
- `agents.orchestrator.event_manager.update_event_status()`
- `agents.orchestrator.event_manager.correlate_feedback_event()`
- `agents.orchestrator.event_manager.list_events()`
- `agents.orchestrator.approval_gate.mark_for_approval()`
- `agents.orchestrator.approval_gate.approve_action()`
- `agents.orchestrator.approval_gate.reject_action()`
- `agents.orchestrator.approval_gate.skip_approval()`
- `agents.orchestrator.approval_gate.get_approval_status()`
- `agents.orchestrator.approval_gate.is_approved()`
- `agents.orchestrator.approval_gate.is_rejected()`
- `agents.orchestrator.approval_gate.list_pending_approvals()`
- `agents.orchestrator.audit_logger.log_action()`
- `agents.orchestrator.audit_logger.log_approval_request()`
- `agents.orchestrator.audit_logger.log_approval_decision()`
- `agents.orchestrator.audit_logger.log_execution()`
- `agents.orchestrator.audit_logger.log_outcome()`
- `agents.orchestrator.audit_logger.log_feedback()`
- `agents.orchestrator.audit_logger.read_audit_trail()`
- `agents.orchestrator.audit_logger.set_audit_log_file()`
- `agents.orchestrator.audit_logger.export_audit_trail()`
- `agents.orchestrator.router.route_command_with_gates()`
- `agents.orchestrator.orchestrator.get_event_registry_snapshot()`

#### Enhanced Public APIs
- `agents.orchestrator.router.RoutedTask` (added event_id, requires_approval, approval_reason)
- `agents.orchestrator.router.route_command()` (now generates event_id, logs action)
- `agents.orchestrator.orchestrator.run_with_routing()` (now logs execution/outcome)
- `agents.orchestrator.worker_base.BaseWorker.run()` (now logs outcomes)

### Dependencies

**Added:** None (uses only Python stdlib: json, datetime, enum, uuid, zoneinfo)

**Removed:** None

### Backward Compatibility

✅ **100% Backward Compatible**
- No breaking changes to existing APIs
- All existing code continues to work
- New functionality is opt-in
- Old routing API still available

### Testing

**Unit Tests:** 18/18 pass ✓
- Event ID generation
- Event context tracking
- Approval gate workflow
- Audit trail operations
- Router integration

**Smoke Tests:** 5/5 pass ✓
- Basic event flow
- Approval gates
- Audit trail
- Router integration
- End-to-end workflow

**Syntax Checks:** ✓ All files compile without errors

**Import Checks:** ✓ All imports resolve correctly

### Known Issues

None. All MVP objectives achieved.

### Known Limitations

1. **In-memory storage** — Event registry, approvals, and audit trail live in RAM
   - Mitigation: Set `audit_log_file` for optional file persistence
   - Future: Phase 2 will add SQLite persistence

2. **No notifications** — No alerts for pending approvals
   - Future: Phase 3 will add Telegram/email notifications

3. **All actions auto-approved (MVP)** — No policy-based approval decisions
   - Future: Phase 4 will add approval policies

4. **No analytics** — No tracking of approval patterns/outcomes
   - Future: Phase 5 will add learning loop integration

### Security Considerations

- Event IDs are unique but predictable (timestamp + UUID)
- Audit trail is append-only but not signed/encrypted
- In-memory storage vulnerable to process restart/crash
- Future: Add encryption, persistent storage, signature verification

### Performance Impact

- Minimal overhead: Event ID generation is O(1), logging is O(1) appends
- Memory growth: ~500 bytes per event + approval + audit entries
- No impact on existing command_handler performance

### Deployment Notes

1. **Zero downtime** — Deploy immediately, no migration needed
2. **No config changes** — Works with existing setup
3. **Optional features** — Use `route_command_with_gates()` to enable tracking
4. **Monitoring** — Call `get_event_registry_snapshot()` to check status

### Future Work

#### Phase 2: Persistent Storage
- SQLite for event/approval/audit data
- Query/export endpoints
- Retention policies

#### Phase 3: Notification & Escalation
- Telegram notifications for pending approvals
- Email summaries
- Escalation for long-pending decisions

#### Phase 4: Policy Engine
- Define approval policies (by command, user, tier)
- Auto-approve low-risk actions
- Auto-reject high-risk from untrusted users
- Appeals workflow

#### Phase 5: Analytics & Learning
- Track decision patterns
- Correlate with outcomes
- Use feedback to improve policies

### Contributors

- Event System MVP implementation
- Test suite (18 unit tests + 5 smoke tests)
- Documentation (EVENT_SYSTEM.md + MVP_SUMMARY.md)

### References

- See `EVENT_SYSTEM.md` for complete API reference
- See `MVP_SUMMARY.md` for high-level overview
- See `tests/test_event_system.py` for usage examples
- See `tests/smoke_test_event_system.py` for integration tests
