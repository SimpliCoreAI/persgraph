#!/usr/bin/env python
"""
Smoke test for the event system integration.

Verifies:
  1. Event ID generation
  2. Approval gates
  3. Audit trail logging
  4. Router integration
  5. Worker integration (mock)
  6. End-to-end flow

Run with: .venv/bin/python tests/smoke_test_event_system.py
"""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.orchestrator.event_manager import generate_event_id, get_event_context
from agents.orchestrator.approval_gate import (
    mark_for_approval,
    approve_action,
    is_approved,
    list_pending_approvals,
)
from agents.orchestrator.audit_logger import (
    log_action,
    log_approval_decision,
    log_execution,
    log_outcome,
    read_audit_trail,
    get_audit_trail_size,
    clear_audit_trail,
)
from agents.orchestrator.router import route_command_with_gates


def test_basic_event_flow():
    """Test: Event generation and tracking."""
    print("\n[TEST 1] Event generation and tracking...")
    
    event_id = generate_event_id("inbox_triage", "/note", user_id="test_user")
    ctx = get_event_context(event_id)
    
    assert event_id.startswith("evt_"), "Event ID should start with evt_"
    assert ctx["worker_type"] == "inbox_triage", "Worker type mismatch"
    assert ctx["command"] == "/note", "Command mismatch"
    assert ctx["status"] == "created", "Initial status should be 'created'"
    
    print(f"  ✓ Event ID generated: {event_id}")
    print(f"  ✓ Event context tracked: {ctx['worker_type']} / {ctx['command']}")


def test_approval_gates():
    """Test: Approval gate workflow."""
    print("\n[TEST 2] Approval gate workflow...")
    
    event_id = generate_event_id("inbox_triage", "/note", user_id="test_user")
    
    # Mark for approval
    success = mark_for_approval(
        event_id,
        "/note",
        "test",
        reason="High-risk action",
    )
    assert success, "Failed to mark for approval"
    print("  ✓ Action marked for approval")
    
    # List pending
    pending = list_pending_approvals(limit=10)
    assert len(pending) == 1, "Should have 1 pending approval"
    print(f"  ✓ Pending approvals listed: {len(pending)} actions")
    
    # Approve
    success = approve_action(event_id, approved_by="admin")
    assert success, "Failed to approve"
    assert is_approved(event_id), "Should be approved"
    print("  ✓ Action approved")
    
    # Should not appear in pending anymore
    pending = list_pending_approvals(limit=10)
    assert len(pending) == 0, "Should have no pending approvals"
    print("  ✓ No longer pending after approval")


def test_audit_trail():
    """Test: Audit trail logging and querying."""
    print("\n[TEST 3] Audit trail logging and querying...")
    
    clear_audit_trail()
    assert get_audit_trail_size() == 0, "Trail should start empty"
    
    event_id = generate_event_id("inbox_triage", "/note", user_id="test_user")
    
    # Log action
    log_action(event_id, "test_user", "/note", "buy groceries", worker_type="inbox_triage")
    assert get_audit_trail_size() == 1, "Should have 1 entry"
    print("  ✓ Action logged")
    
    # Log execution
    log_execution(event_id, "inbox_triage")
    assert get_audit_trail_size() == 2, "Should have 2 entries"
    print("  ✓ Execution logged")
    
    # Log outcome
    log_outcome(event_id, "completed", "✓ Note saved", worker_type="inbox_triage")
    assert get_audit_trail_size() == 3, "Should have 3 entries"
    print("  ✓ Outcome logged")
    
    # Query by event_id
    trail = read_audit_trail(event_id=event_id)
    assert len(trail) == 3, "Should retrieve all 3 entries"
    assert trail[0]["event_type"] == "action_created"
    assert trail[2]["event_type"] == "action_completed"
    print(f"  ✓ Audit trail queried: {len(trail)} entries")
    print(f"    - {trail[0]['event_type']}")
    print(f"    - {trail[1]['event_type']}")
    print(f"    - {trail[2]['event_type']}")


def test_router_integration():
    """Test: Router generates and injects event IDs."""
    print("\n[TEST 4] Router integration...")
    
    user_context = {"id": "test_user", "name": "Test User", "tier": "user"}
    
    routed = route_command_with_gates("/note buy groceries", user_context)
    
    assert routed.event_id.startswith("evt_"), "Event ID missing"
    assert routed.payload["event_id"] == routed.event_id, "Event ID not in payload"
    assert routed.command == "/note", "Command not routed"
    assert routed.args == "buy groceries", "Args not preserved"
    assert routed.requires_approval is False, "MVP: no approvals needed"
    
    print(f"  ✓ Command routed with event_id: {routed.event_id}")
    print(f"  ✓ Payload includes event_id: {routed.payload['event_id']}")
    print(f"  ✓ Approval gate skipped (MVP low-risk)")
    
    # Verify audit trail was created
    trail = read_audit_trail(event_id=routed.event_id)
    assert len(trail) >= 1, "Audit trail should have at least 1 entry"
    print(f"  ✓ Audit trail created: {len(trail)} entries")


def test_end_to_end_flow():
    """Test: Full end-to-end flow."""
    print("\n[TEST 5] End-to-end flow...")
    
    clear_audit_trail()
    
    # 1. Route command
    print("  Step 1: Route command")
    user_context = {"id": "alice", "name": "Alice", "tier": "user"}
    routed = route_command_with_gates("/note meeting at 2pm", user_context)
    event_id = routed.event_id
    print(f"    ✓ Command routed with event_id: {event_id}")
    
    # 2. Check approval (should be skipped in MVP)
    print("  Step 2: Check approval")
    assert not routed.requires_approval, "MVP: no approvals"
    print("    ✓ Approval skipped (low-risk)")
    
    # 3. Simulate execution
    print("  Step 3: Simulate execution")
    log_execution(event_id, "inbox_triage", status="executing")
    print("    ✓ Execution logged")
    
    # 4. Simulate outcome
    print("  Step 4: Log outcome")
    result = "✓ Note 'meeting at 2pm' saved to inbox"
    log_outcome(event_id, "completed", result, worker_type="inbox_triage")
    print(f"    ✓ Outcome logged: {result}")
    
    # 5. Query full trail
    print("  Step 5: Query audit trail")
    trail = read_audit_trail(event_id=event_id)
    print(f"    ✓ Audit trail has {len(trail)} entries:")
    for i, entry in enumerate(trail, 1):
        print(f"      {i}. {entry['event_type']}")
    
    # 6. Verify event context
    print("  Step 6: Verify event context")
    ctx = get_event_context(event_id)
    assert ctx["status"] == "approved", "Status should be approved (skipped gate)"
    assert ctx["approval_state"] == "skipped", "Approval state should be skipped"
    print(f"    ✓ Event status: {ctx['status']}")
    print(f"    ✓ Approval state: {ctx['approval_state']}")


def main():
    """Run all smoke tests."""
    print("\n" + "=" * 70)
    print("EVENT SYSTEM MVP — SMOKE TESTS")
    print("=" * 70)
    
    try:
        test_basic_event_flow()
        test_approval_gates()
        test_audit_trail()
        test_router_integration()
        test_end_to_end_flow()
        
        print("\n" + "=" * 70)
        print("✓ ALL SMOKE TESTS PASSED")
        print("=" * 70)
        return 0
    
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
