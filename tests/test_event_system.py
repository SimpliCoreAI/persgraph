"""
Integration tests for event system, approval gates, and audit trail.

Tests:
  1. Event ID generation and tracking
  2. Approval gate marking and decision
  3. Audit trail logging and querying
  4. Feedback loop correlation
"""

import pytest
from datetime import datetime
from zoneinfo import ZoneInfo

# Test imports
from agents.orchestrator.event_manager import (
    generate_event_id,
    get_event_context,
    update_event_status,
    correlate_feedback_event,
    list_events,
    clear_event_registry,
)
from agents.orchestrator.approval_gate import (
    mark_for_approval,
    approve_action,
    reject_action,
    skip_approval,
    get_approval_status,
    is_approved,
    is_rejected,
    list_pending_approvals,
    clear_approval_registry,
)
from agents.orchestrator.audit_logger import (
    log_action,
    log_approval_request,
    log_approval_decision,
    log_execution,
    log_outcome,
    log_feedback,
    read_audit_trail,
    clear_audit_trail,
    get_audit_trail_size,
)
from agents.orchestrator.router import route_command, route_command_with_gates


@pytest.fixture(autouse=True)
def cleanup_registries():
    """Clean up all registries before and after each test."""
    clear_event_registry()
    clear_approval_registry()
    clear_audit_trail()
    yield
    clear_event_registry()
    clear_approval_registry()
    clear_audit_trail()


class TestEventManager:
    """Test event ID generation and tracking."""

    def test_generate_event_id(self):
        """Test generating a unique event ID."""
        event_id = generate_event_id(
            "inbox_triage",
            "/note",
            user_id="12345",
        )

        assert event_id.startswith("evt_")
        assert len(event_id) == 27  # evt_YYYYMMDDHHMMSS_xxxxxxxx

    def test_event_context_tracking(self):
        """Test that event context is stored and retrievable."""
        event_id = generate_event_id(
            "inbox_triage",
            "/note",
            user_id="12345",
        )

        ctx = get_event_context(event_id)
        assert ctx is not None
        assert ctx["event_id"] == event_id
        assert ctx["worker_type"] == "inbox_triage"
        assert ctx["command"] == "/note"
        assert ctx["user_id"] == "12345"
        assert ctx["status"] == "created"

    def test_update_event_status(self):
        """Test updating event status."""
        event_id = generate_event_id("inbox_triage", "/note", user_id="12345")

        # Update to pending approval
        success = update_event_status(event_id, "pending_approval", approval_state="pending")
        assert success is True

        ctx = get_event_context(event_id)
        assert ctx["status"] == "pending_approval"
        assert ctx["approval_state"] == "pending"

    def test_correlate_feedback_event(self):
        """Test correlating feedback to original event."""
        event_id = generate_event_id("inbox_triage", "/note", user_id="12345")
        feedback_id = generate_event_id("orchestrator", "feedback", user_id="12345")

        success = correlate_feedback_event(event_id, feedback_id)
        assert success is True

        ctx = get_event_context(event_id)
        assert ctx["feedback_event_id"] == feedback_id

    def test_list_events_filtering(self):
        """Test listing events with filtering."""
        # Create multiple events
        evt1 = generate_event_id("inbox_triage", "/note", user_id="user1")
        evt2 = generate_event_id("calendar_prep", "/appointment", user_id="user2")
        evt3 = generate_event_id("inbox_triage", "/task", user_id="user1")

        # Update statuses
        update_event_status(evt1, "pending_approval")
        update_event_status(evt2, "completed")

        # List by status
        pending = list_events(status="pending_approval", limit=10)
        assert len(pending) == 1
        assert pending[0]["event_id"] == evt1

        # List by user
        user1_events = list_events(user_id="user1", limit=10)
        assert len(user1_events) == 2


class TestApprovalGate:
    """Test human approval gates."""

    def test_mark_for_approval(self):
        """Test marking an action for approval."""
        event_id = generate_event_id("inbox_triage", "/note", user_id="12345")

        success = mark_for_approval(
            event_id,
            "/note",
            "buy groceries",
            reason="User tier restricted",
        )
        assert success is True

        approval = get_approval_status(event_id)
        assert approval is not None
        assert approval["state"] == "pending"
        assert approval["command"] == "/note"

    def test_approve_action(self):
        """Test approving a pending action."""
        event_id = generate_event_id("inbox_triage", "/note", user_id="12345")
        mark_for_approval(event_id, "/note", "test", reason="test")

        success = approve_action(event_id, approved_by="admin", reason="OK")
        assert success is True

        approval = get_approval_status(event_id)
        assert approval["state"] == "approved"
        assert approval["decided_by"] == "admin"
        assert is_approved(event_id) is True
        assert is_rejected(event_id) is False

    def test_reject_action(self):
        """Test rejecting a pending action."""
        event_id = generate_event_id("inbox_triage", "/note", user_id="12345")
        mark_for_approval(event_id, "/note", "test", reason="test")

        success = reject_action(event_id, reason="Too risky", rejected_by="admin")
        assert success is True

        approval = get_approval_status(event_id)
        assert approval["state"] == "rejected"
        assert approval["decided_by"] == "admin"
        assert is_rejected(event_id) is True
        assert is_approved(event_id) is False

    def test_skip_approval(self):
        """Test skipping approval for low-risk actions."""
        event_id = generate_event_id("inbox_triage", "/note", user_id="12345")

        success = skip_approval(event_id, reason="Low-risk")
        assert success is True

        approval = get_approval_status(event_id)
        assert approval["state"] == "skipped"
        assert is_approved(event_id) is True

    def test_list_pending_approvals(self):
        """Test listing pending approvals."""
        evt1 = generate_event_id("inbox_triage", "/note", user_id="user1")
        evt2 = generate_event_id("calendar_prep", "/appointment", user_id="user2")
        evt3 = generate_event_id("inbox_triage", "/task", user_id="user1")

        # Mark some for approval
        mark_for_approval(evt1, "/note", "test1", requires_human=True)
        mark_for_approval(evt2, "/appointment", "test2", requires_human=True)
        approve_action(evt2)  # Approve one

        # List should only return pending
        pending = list_pending_approvals(requires_human=True, limit=50)
        assert len(pending) == 1
        assert pending[0]["event_id"] == evt1


class TestAuditLogger:
    """Test audit trail logging and querying."""

    def test_log_action(self):
        """Test logging an action event."""
        event_id = generate_event_id("inbox_triage", "/note", user_id="12345")

        log_action(
            event_id,
            "12345",
            "/note",
            "buy groceries",
            worker_type="inbox_triage",
        )

        trail = read_audit_trail(event_id=event_id)
        assert len(trail) == 1
        assert trail[0]["event_type"] == "action_created"
        assert trail[0]["command"] == "/note"

    def test_log_approval_flow(self):
        """Test logging approval request and decision."""
        event_id = generate_event_id("inbox_triage", "/note", user_id="12345")

        # Log action
        log_action(event_id, "12345", "/note", "test")

        # Log approval request
        log_approval_request(event_id, "/note", "risky action", requested_by="system")

        # Log approval decision
        log_approval_decision(event_id, "approved", "admin", reason="safe enough")

        trail = read_audit_trail(event_id=event_id)
        assert len(trail) == 3
        assert trail[0]["event_type"] == "action_created"
        assert trail[1]["event_type"] == "approval_requested"
        assert trail[2]["event_type"] == "approval_granted"

    def test_log_outcome(self):
        """Test logging action outcome."""
        event_id = generate_event_id("inbox_triage", "/note", user_id="12345")

        log_action(event_id, "12345", "/note", "test")
        log_execution(event_id, "inbox_triage", status="executing")
        log_outcome(
            event_id,
            "completed",
            "✓ Note saved",
            worker_type="inbox_triage",
        )

        trail = read_audit_trail(event_id=event_id)
        assert len(trail) == 3
        assert trail[2]["event_type"] == "action_completed"
        assert trail[2]["result"] == "✓ Note saved"

    def test_read_audit_trail_filtering(self):
        """Test querying audit trail with filters."""
        evt1 = generate_event_id("inbox_triage", "/note", user_id="user1")
        evt2 = generate_event_id("calendar_prep", "/appointment", user_id="user2")

        log_action(evt1, "user1", "/note", "test1", worker_type="inbox_triage")
        log_action(evt2, "user2", "/appointment", "test2", worker_type="calendar_prep")

        # Filter by event_id
        trail1 = read_audit_trail(event_id=evt1)
        assert len(trail1) == 1
        assert trail1[0]["event_id"] == evt1

        # Filter by user_id
        user_trail = read_audit_trail(user_id="user1")
        assert all(e["user_id"] == "user1" for e in user_trail)

    def test_audit_trail_size(self):
        """Test audit trail size tracking."""
        assert get_audit_trail_size() == 0

        event_id = generate_event_id("inbox_triage", "/note", user_id="12345")
        log_action(event_id, "12345", "/note", "test")
        assert get_audit_trail_size() == 1

        log_execution(event_id, "inbox_triage")
        assert get_audit_trail_size() == 2


class TestRouterIntegration:
    """Test router integration with event system."""

    def test_route_command_generates_event_id(self):
        """Test that route_command generates event_id in payload."""
        user_context = {"id": "12345", "name": "user", "tier": "user"}

        routed = route_command("/note buy groceries", user_context)

        assert routed.event_id.startswith("evt_")
        assert len(routed.event_id) == 27
        assert routed.payload["event_id"] == routed.event_id
        assert routed.command == "/note"

    def test_route_command_with_gates(self):
        """Test route_command_with_gates applies approval gates."""
        user_context = {"id": "12345", "name": "user", "tier": "user"}

        routed = route_command_with_gates("/note buy groceries", user_context)

        # MVP skips approval for all actions
        assert routed.requires_approval is False

        # But approval should be recorded
        approval = get_approval_status(routed.event_id)
        assert approval is not None
        assert approval["state"] == "skipped"

    def test_route_command_with_gates_logs_action(self):
        """Test that route_command_with_gates logs to audit trail."""
        user_context = {"id": "12345", "name": "user", "tier": "user"}

        routed = route_command_with_gates("/note buy groceries", user_context)

        trail = read_audit_trail(event_id=routed.event_id)
        assert len(trail) >= 1
        assert trail[0]["event_type"] == "action_created"
        assert trail[0]["command"] == "/note"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
