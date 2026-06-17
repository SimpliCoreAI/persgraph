"""
Tests for the response_feedback module.

Covers: response ID emission, metadata capture, no regression for existing IDs.
"""

import json
import importlib
from pathlib import Path
from datetime import datetime, timezone

import pytest


@pytest.fixture()
def response_feedback_setup(tmp_path, monkeypatch):
    """Setup response_feedback and learning_db with temp DB."""
    import second_brain.learning_db as learning_db
    import second_brain.response_feedback as response_feedback

    db_path = tmp_path / "learning.db"
    monkeypatch.setattr(learning_db, "DB_PATH", db_path)
    
    return learning_db, response_feedback, db_path


def test_record_response_feedback_returns_event_id(response_feedback_setup):
    """Test that response feedback returns a valid event ID."""
    learning_db, response_feedback, _ = response_feedback_setup
    
    response_text = "This is a test response"
    resp, event_id = response_feedback.record_response_feedback(
        response_text,
        command="/ask",
        user_id="test_user"
    )
    
    assert resp == response_text  # Original text unchanged
    assert event_id  # ID is non-empty
    assert len(event_id) == 36  # UUID format


def test_record_response_feedback_stores_metadata(response_feedback_setup):
    """Test that metadata is captured in the stored event."""
    learning_db, response_feedback, _ = response_feedback_setup
    
    response_feedback.record_response_feedback(
        "Test response",
        command="/note",
        user_id="user123",
        metadata={"latency_ms": 456, "status": "success"}
    )
    
    # Query the stored events
    events = learning_db.get_event_summary(limit=10)
    
    assert len(events) >= 1
    event = events[0]
    assert event["event_type"] == "response"
    metadata = event.get("metadata", {})
    assert metadata.get("command") == "/note"
    assert metadata.get("user_id") == "user123"
    assert metadata.get("latency_ms") == 456


def test_format_response_with_feedback_appends_id(response_feedback_setup):
    """Test that format_response_with_feedback appends the ID."""
    _, response_feedback, _ = response_feedback_setup
    
    response_text = "Original response"
    event_id = "abc-123-def"
    
    formatted = response_feedback.format_response_with_feedback(
        response_text,
        event_id,
        include_id=True
    )
    
    assert response_text in formatted
    assert event_id in formatted
    assert "Response ID:" in formatted


def test_format_response_with_feedback_no_id(response_feedback_setup):
    """Test that format_response_with_feedback doesn't modify when include_id=False."""
    _, response_feedback, _ = response_feedback_setup
    
    response_text = "Original response"
    event_id = "abc-123-def"
    
    formatted = response_feedback.format_response_with_feedback(
        response_text,
        event_id,
        include_id=False
    )
    
    assert formatted == response_text
    assert event_id not in formatted


def test_wrap_response_one_shot(response_feedback_setup):
    """Test wrap_response convenience wrapper."""
    learning_db, response_feedback, _ = response_feedback_setup
    
    response_text = "Wrapped response"
    wrapped = response_feedback.wrap_response(
        response_text,
        command="/ask",
        user_id="user_xyz"
    )
    
    # Should not include ID in response text by default
    assert wrapped == response_text
    
    # But event should be recorded
    events = learning_db.get_event_summary(limit=10)
    assert len(events) >= 1
    assert any(e["event_type"] == "response" for e in events)


def test_wrap_response_with_id_in_text(response_feedback_setup):
    """Test wrap_response with include_id_in_response=True."""
    _, response_feedback, _ = response_feedback_setup
    
    response_text = "Response to wrap"
    wrapped = response_feedback.wrap_response(
        response_text,
        command="/note",
        include_id_in_response=True
    )
    
    # ID should be included in response
    assert response_text in wrapped
    assert "Response ID:" in wrapped


def test_no_regression_for_existing_command_event_ids(response_feedback_setup):
    """Test that response feedback doesn't interfere with command event IDs."""
    learning_db, response_feedback, _ = response_feedback_setup
    
    # Simulate a command that records its own event ID
    command_event_id = learning_db.record_event(
        event_type="command_usage",
        metadata={"command": "/ingest"}
    )
    
    # Then record response feedback for the same response
    response_text = "Command response"
    response_event_id = response_feedback.record_response_feedback(
        response_text,
        command="/ingest"
    )[1]
    
    # Both IDs should exist and be distinct
    assert command_event_id
    assert response_event_id
    assert command_event_id != response_event_id
    
    # Both should be queryable
    events = learning_db.get_event_summary(limit=100)
    event_types = [e["event_type"] for e in events]
    assert "command_usage" in event_types
    assert "response" in event_types


def test_response_feedback_with_morning_brief_event_id(response_feedback_setup):
    """Test that response feedback works alongside briefing event IDs."""
    learning_db, response_feedback, _ = response_feedback_setup
    
    # Simulate briefing event
    briefing_event_id = learning_db.record_event(
        event_type="command_usage",
        metadata={"command": "/briefing"}
    )
    
    # Record response feedback for briefing response
    briefing_text = "Weekly briefing output..."
    response_event_id = response_feedback.record_response_feedback(
        briefing_text,
        command="/briefing"
    )[1]
    
    # Verify both are recorded
    events = learning_db.get_event_summary(limit=100)
    ids = {e["id"] for e in events}
    
    assert briefing_event_id in ids
    assert response_event_id in ids
    assert len(ids) >= 2


def test_response_feedback_stats(response_feedback_setup):
    """Test get_response_feedback_stats()."""
    learning_db, response_feedback, _ = response_feedback_setup
    
    # Record several response events
    for i in range(3):
        response_feedback.record_response_feedback(
            f"Response {i}",
            command="/ask"
        )
    
    # Get stats
    stats = response_feedback.get_response_feedback_stats()
    
    assert stats["response_feedback_count"] >= 3
    assert "response" in stats["all_event_counts"]


def test_response_feedback_text_length_captured(response_feedback_setup):
    """Test that response text length is captured as metadata."""
    learning_db, response_feedback, _ = response_feedback_setup
    
    long_response = "x" * 5000
    response_feedback.record_response_feedback(
        long_response,
        command="/digest"
    )
    
    events = learning_db.get_event_summary(limit=10)
    event = events[0]
    metadata = event.get("metadata", {})
    
    assert metadata.get("response_length") == 5000


def test_response_feedback_handles_none_values(response_feedback_setup):
    """Test that response_feedback handles None user_id and metadata gracefully."""
    _, response_feedback, _ = response_feedback_setup
    
    resp, event_id = response_feedback.record_response_feedback(
        "Test",
        command="/ask",
        user_id=None,
        metadata=None
    )
    
    assert resp == "Test"
    assert event_id  # Should still produce an ID


def test_response_feedback_multiple_calls_produce_distinct_ids(response_feedback_setup):
    """Test that multiple calls produce distinct event IDs."""
    _, response_feedback, _ = response_feedback_setup
    
    ids = []
    for i in range(5):
        _, event_id = response_feedback.record_response_feedback(
            f"Response {i}",
            command="/note"
        )
        ids.append(event_id)
    
    # All IDs should be unique
    assert len(set(ids)) == 5
    assert all(ids)  # All non-empty


def test_response_feedback_safe_no_breaking_changes(response_feedback_setup):
    """Test that response_feedback is a pure wrapper (no side effects on command behavior)."""
    _, response_feedback, _ = response_feedback_setup
    
    # Simulate various response types
    responses = [
        "Short",
        "A somewhat longer response that contains multiple words",
        "",  # Empty response
        "Response with special chars: !@#$%^&*()",
        "Multi\nline\nresponse",
    ]
    
    for resp in responses:
        # wrap_response should not modify the text (when include_id_in_response=False)
        wrapped = response_feedback.wrap_response(resp, command="/test")
        assert wrapped == resp
        
        # format without ID
        formatted = response_feedback.format_response_with_feedback(
            resp, "some-id", include_id=False
        )
        assert formatted == resp
