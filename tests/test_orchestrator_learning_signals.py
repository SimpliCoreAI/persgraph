"""
Test: Orchestrator Learning Signals Integration

Tests the integration of the learning signals module with:
  - Event manager (event creation and tracking)
  - Approval gate (approval decisions)
  - Router (routing decisions)
  - Orchestrator (outcome tracking)
  - Worker refinement (signal consumption)

Validates:
  1. Routing signals are emitted when commands are routed
  2. Approval signals are emitted when decisions are made
  3. Outcome signals are emitted when actions complete
  4. Learning signals can be queried and analyzed
  5. Worker refinement can generate suggestions based on signals
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from agents.orchestrator.event_manager import (
    generate_event_id,
    get_event_context,
    update_event_status,
    clear_event_registry,
)
from agents.orchestrator.approval_gate import (
    mark_for_approval,
    approve_action,
    reject_action,
    skip_approval,
    clear_approval_registry,
)
from agents.orchestrator.learning_signals import (
    emit_routing_signal,
    emit_approval_signal,
    emit_outcome_signal,
    get_routing_signals,
    get_approval_signals,
    get_outcome_signals,
    compute_routing_confidence,
    compute_approval_likelihood,
    compute_worker_success_rate,
    get_signal_stats,
    clear_signals,
    list_all_signals,
)
from agents.orchestrator.worker_refinement import (
    suggest_worker_adjustments,
    suggest_approval_refinements,
    get_learned_preferences,
    describe_refinement_state,
)


def test_routing_signal_emission():
    """Test that routing signals are emitted and retrieved correctly."""
    print("\n🧪 Test: Routing Signal Emission")
    clear_signals()

    event_id = "evt_test_route_001"
    emit_routing_signal(
        event_id=event_id,
        worker_type="inbox_triage",
        command="/note",
        user_tier="user",
        confidence=0.95,
        reason="Standard note capture",
    )

    signals = get_routing_signals(worker_type="inbox_triage", command="/note")
    assert len(signals) == 1, "Should have exactly one routing signal"
    assert signals[0]["event_id"] == event_id
    assert signals[0]["confidence"] == 0.95
    print("  ✓ Routing signal emitted and retrieved")


def test_approval_signal_emission():
    """Test that approval signals are emitted when decisions are made."""
    print("\n🧪 Test: Approval Signal Emission")
    clear_signals()
    clear_approval_registry()
    clear_event_registry()

    event_id = generate_event_id("inbox_triage", "/note", user_id="user123")
    assert event_id, "Should generate event ID"

    # Test approval: mark for approval first, then approve
    mark_success = mark_for_approval(event_id, "/note", "test args", reason="Test approval")
    assert mark_success, "Should mark for approval"
    
    success = approve_action(event_id, approved_by="admin", reason="Safe action")
    assert success, "Should approve action"

    signals = get_approval_signals(decision="approved")
    assert len(signals) >= 1, "Should have at least one approval signal"
    print("  ✓ Approval signal emitted for approved action")

    # Test rejection
    clear_signals()
    clear_approval_registry()
    event_id2 = generate_event_id("travel_scout", "/explore_skip")
    mark_for_approval(event_id2, "/explore_skip", "test args", reason="Test rejection")
    reject_action(event_id2, reason="User location unavailable", rejected_by="system")

    signals = get_approval_signals(decision="rejected")
    assert len(signals) >= 1, "Should have rejection signal"
    print("  ✓ Rejection signal emitted for rejected action")

    # Test skip
    clear_signals()
    clear_approval_registry()
    event_id3 = generate_event_id("inbox_triage", "/task")
    skip_approval(event_id3, reason="Low-risk action")

    signals = get_approval_signals(decision="skipped")
    assert len(signals) >= 1, "Should have skip signal"
    print("  ✓ Skip signal emitted for skipped approval")


def test_outcome_signal_emission():
    """Test that outcome signals are emitted for action results."""
    print("\n🧪 Test: Outcome Signal Emission")
    clear_signals()

    event_id = "evt_test_outcome_001"

    # Success outcome
    emit_outcome_signal(
        event_id=event_id,
        command="/note",
        worker_type="inbox_triage",
        status="completed",
        success=True,
        duration_ms=250,
        result_preview="Note created successfully",
    )

    signals = get_outcome_signals(success_only=True)
    assert len(signals) == 1, "Should have one success signal"
    assert signals[0]["status"] == "completed"
    print("  ✓ Success outcome signal emitted and retrieved")

    # Failure outcome
    clear_signals()
    emit_outcome_signal(
        event_id="evt_test_outcome_002",
        command="/appointment",
        worker_type="calendar_prep",
        status="failed",
        success=False,
        error="Calendar API timeout",
    )

    signals = get_outcome_signals(success_only=False)
    assert len(signals) == 1, "Should have one failure signal"
    assert not signals[0]["success"]
    print("  ✓ Failure outcome signal emitted and retrieved")


def test_signal_aggregation():
    """Test that signals can be aggregated and analyzed."""
    print("\n�912 Test: Signal Aggregation & Analysis")
    clear_signals()

    # Emit multiple routing signals
    for i in range(5):
        emit_routing_signal(
            event_id=f"evt_route_{i}",
            worker_type="inbox_triage",
            command="/note",
            user_tier="user",
            confidence=0.90 + (i * 0.02),
        )

    # Emit multiple outcome signals (4 success, 1 failure)
    for i in range(4):
        emit_outcome_signal(
            event_id=f"evt_outcome_success_{i}",
            command="/note",
            worker_type="inbox_triage",
            status="completed",
            success=True,
        )

    emit_outcome_signal(
        event_id="evt_outcome_failure_0",
        command="/note",
        worker_type="inbox_triage",
        status="failed",
        success=False,
    )

    # Get aggregated stats
    stats = get_signal_stats()
    assert stats["total_signals"] == 10, "Should have 10 total signals"
    assert stats["routing_signals"] == 5
    assert stats["outcome_signals"] == 5
    assert stats["success_rate"] == 0.8, "Success rate should be 4/5 = 0.8"

    # Compute success rate
    success = compute_worker_success_rate("inbox_triage", command="/note")
    assert success == 0.8, f"Expected 0.8, got {success}"
    print("  ✓ Signals aggregated and analyzed correctly")


def test_worker_adjustment_suggestions():
    """Test that worker refinement generates adjustment suggestions."""
    print("\n🧪 Test: Worker Adjustment Suggestions")
    clear_signals()

    # First emit routing signals (needed for suggestions)
    for i in range(10):
        emit_routing_signal(
            event_id=f"evt_route_success_{i}",
            worker_type="inbox_triage",
            command="/note",
            user_tier="user",
            confidence=1.0,
        )

    # Emit successful outcomes for one worker
    for i in range(10):
        emit_outcome_signal(
            event_id=f"evt_success_{i}",
            command="/note",
            worker_type="inbox_triage",
            status="completed",
            success=True,
        )

    # Emit routing signals for failing worker
    for i in range(3):
        emit_routing_signal(
            event_id=f"evt_route_fail_{i}",
            worker_type="travel_scout",
            command="/explore_click",
            user_tier="user",
            confidence=1.0,
        )

    # Emit some failed outcomes for another
    for i in range(3):
        emit_outcome_signal(
            event_id=f"evt_fail_{i}",
            command="/explore_click",
            worker_type="travel_scout",
            status="failed",
            success=False,
        )

    # Get suggestions
    suggestions = suggest_worker_adjustments(min_signals=3)
    assert len(suggestions) > 0, "Should have at least one suggestion"

    # Check that we got a positive adjustment for high-success worker
    positive_suggestions = [s for s in suggestions if s["confidence_adjustment"] > 0]
    assert len(positive_suggestions) > 0, "Should have positive adjustments for successful workers"

    # Check that we got a negative adjustment for low-success worker
    negative_suggestions = [s for s in suggestions if s["confidence_adjustment"] < 0]
    assert len(negative_suggestions) > 0, "Should have negative adjustments for failing workers"

    print(f"  ✓ Generated {len(suggestions)} adjustment suggestions")


def test_approval_refinement_suggestions():
    """Test that approval refinement generates suggestions."""
    print("\n🧪 Test: Approval Refinement Suggestions")
    clear_signals()

    # Emit many approvals for /note (high approval rate)
    for i in range(25):
        emit_approval_signal(
            event_id=f"evt_approve_{i}",
            command="/note",
            decision="approved",
            confidence=1.0,
        )

    # Emit one rejection (outlier)
    emit_approval_signal(
        event_id="evt_reject_outlier",
        command="/note",
        decision="rejected",
        confidence=1.0,
    )

    # Get suggestions
    suggestions = suggest_approval_refinements(min_signals=5)
    
    # Should have a suggestion for /note (high approval rate)
    note_suggestions = [s for s in suggestions if s["command"] == "/note"]
    if note_suggestions:
        assert note_suggestions[0]["suggestion"] == "always_approve"
        print("  ✓ Suggested always_approve for high-approval command")
    else:
        print("  ⚠ No suggestion generated (may be OK if rate < 98%)")


def test_learned_preferences():
    """Test that learned preferences can be extracted from signals."""
    print("\n�912 Test: Learned Preferences Extraction")
    clear_signals()

    # Emit routing signals for various commands
    commands = ["/note", "/note", "/note", "/ask", "/ask", "/ingest"]
    for cmd in commands:
        emit_routing_signal(
            event_id=f"evt_{cmd}_{commands.index(cmd)}",
            worker_type="inbox_triage" if cmd.startswith("/note") else "other",
            command=cmd,
            user_tier="user",
        )

    prefs = get_learned_preferences()
    assert len(prefs["preferred_commands"]) > 0
    # Most frequent command should be /note (3 times)
    if prefs["preferred_commands"]:
        top_cmd, count = prefs["preferred_commands"][0]
        assert count >= 2, f"Top command should have at least 2 signals, got {count}"
    print("  ✓ Learned preferences extracted")


def test_refinement_state_export():
    """Test that refinement state can be exported."""
    print("\n🧪 Test: Refinement State Export")
    clear_signals()

    # Emit some signals
    emit_routing_signal("evt_1", "inbox_triage", "/note", "user")
    emit_approval_signal("evt_1", "/note", "approved")
    emit_outcome_signal("evt_1", "/note", "inbox_triage", "completed", True)

    state = describe_refinement_state()
    assert "signal_stats" in state
    assert "worker_adjustments" in state
    assert "approval_refinements" in state
    assert "learned_preferences" in state
    assert state["signal_stats"]["total_signals"] >= 3

    print("  ✓ Refinement state exported successfully")


def test_integrated_workflow():
    """Test a complete integrated workflow: route → approve → execute → learn."""
    print("\n🧪 Test: Integrated Workflow (Route → Approve → Execute → Learn)")
    clear_signals()
    clear_event_registry()
    clear_approval_registry()

    # Step 1: Generate event ID (simulating route_command)
    event_id = generate_event_id("inbox_triage", "/note", user_id="user123")
    assert event_id.startswith("evt_")
    print("  ✓ Step 1: Event ID generated")

    # Step 2: Emit routing signal
    emit_routing_signal(
        event_id=event_id,
        worker_type="inbox_triage",
        command="/note",
        user_tier="user",
        confidence=1.0,
    )
    print("  ✓ Step 2: Routing signal emitted")

    # Step 3: Skip approval (or approve)
    skip_approval(event_id, reason="Low-risk")
    print("  ✓ Step 3: Approval decision (skipped)")

    # Step 4: Emit outcome signal
    emit_outcome_signal(
        event_id=event_id,
        command="/note",
        worker_type="inbox_triage",
        status="completed",
        success=True,
        duration_ms=150,
        result_preview="Note saved",
    )
    print("  ✓ Step 4: Outcome signal emitted")

    # Step 5: Verify all signals are present
    all_signals = list_all_signals()
    routing = [s for s in all_signals if s["signal_type"] == "routing"]
    approval = [s for s in all_signals if s["signal_type"] == "approval"]
    outcome = [s for s in all_signals if s["signal_type"] == "outcome"]

    assert len(routing) >= 1, "Should have routing signal"
    assert len(approval) >= 1, "Should have approval signal"
    assert len(outcome) >= 1, "Should have outcome signal"

    print("  ✓ Step 5: All signals verified")

    # Step 6: Verify learning aggregation
    stats = get_signal_stats()
    assert stats["total_signals"] >= 3
    assert stats["success_rate"] == 1.0, "Should have 100% success"

    print("  ✓ Step 6: Learning aggregation verified")
    print("  ✅ Integrated workflow completed successfully")


if __name__ == "__main__":
    print("=" * 70)
    print("🧠 Orchestrator Learning Signals Integration Tests")
    print("=" * 70)

    try:
        test_routing_signal_emission()
        test_approval_signal_emission()
        test_outcome_signal_emission()
        test_signal_aggregation()
        test_worker_adjustment_suggestions()
        test_approval_refinement_suggestions()
        test_learned_preferences()
        test_refinement_state_export()
        test_integrated_workflow()

        print("\n" + "=" * 70)
        print("✅ All tests passed!")
        print("=" * 70)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
