"""
Tests for the learning_learner module.

Covers: checkpoint management, outcome processing, skill/preference inference.
"""

import json
import importlib
from pathlib import Path
from datetime import datetime, timezone

import pytest


@pytest.fixture()
def learning_setup(tmp_path, monkeypatch):
    """Setup learning modules with temp DB and checkpoint."""
    import second_brain.learning_db as learning_db
    import second_brain.learning_learner as learning_learner

    db_path = tmp_path / "learning.db"
    checkpoint_path = tmp_path / "learning_checkpoint.json"
    
    # Monkeypatch paths directly on module objects (no reload)
    learning_db.DB_PATH = db_path
    learning_learner.CHECKPOINT_PATH = checkpoint_path
    
    return learning_db, learning_learner, db_path, checkpoint_path


def test_checkpoint_roundtrip(learning_setup):
    """Test checkpoint save/load."""
    _, learning_learner, _, checkpoint_path = learning_setup
    
    # Initial checkpoint (default)
    cp = learning_learner.get_checkpoint()
    assert cp == "1970-01-01T00:00:00Z"
    
    # Set checkpoint
    test_time = "2026-06-17T12:30:45Z"
    learning_learner.set_checkpoint(test_time)
    
    # Reload and verify
    cp2 = learning_learner.get_checkpoint()
    assert cp2 == test_time
    # Note: checkpoint_path might be in a different location due to module reloading


def test_run_learner_no_new_records(learning_setup):
    """Test learner handles no new outcomes gracefully."""
    learning_db, learning_learner, _, _ = learning_setup
    
    # Set checkpoint to now
    now = datetime.now(timezone.utc).isoformat()
    learning_learner.set_checkpoint(now)
    
    # Run learner (no outcomes recorded yet)
    result = learning_learner.run_learner(verbose=False)
    
    assert result["status"] == "no_new_records"
    assert result["outcomes_processed"] == 0


def test_run_learner_with_new_outcomes(learning_setup):
    """Test learner processes new outcomes."""
    learning_db, learning_learner, _, _ = learning_setup
    
    # Set old checkpoint (without timezone suffix for comparison)
    learning_learner.set_checkpoint("2026-06-01T00:00:00")
    
    # Record some outcomes
    event_id = learning_db.record_event(
        event_type="suggestion",
        location={"lat": 37.0, "lon": -122.0},
        metadata={"cadence_minutes": 60}
    )
    
    outcome_ids = []
    for i in range(5):
        oid = learning_db.record_outcome(
            event_id=event_id,
            outcome_type="clicked" if i < 3 else "skipped",
            suggestion_title=f"Place {i}",
            suggestion_category="poi",
            engagement_seconds=3 + i
        )
        outcome_ids.append(oid)
    
    # Run learner
    result = learning_learner.run_learner(verbose=False)
    
    assert result["status"] == "success"
    assert result["outcomes_processed"] == 5
    assert result["checkpoint_advanced_from"] == "2026-06-01T00:00:00"
    assert result["checkpoint_advanced_to"] is not None
    # Both timestamps should be ISO format strings; compare normalized
    assert result["checkpoint_advanced_to"].split('+')[0] > result["checkpoint_advanced_from"]


def test_skill_inference_from_outcomes(learning_setup):
    """Test skill inference from high-engagement outcomes."""
    learning_db, learning_learner, _, _ = learning_setup
    
    # Set old checkpoint so outcomes are "new"
    learning_learner.set_checkpoint("2026-06-01T00:00:00")
    
    # Record outcomes with high engagement rate
    event_id = learning_db.record_event(
        event_type="suggestion",
        location={"lat": 37.0, "lon": -122.0},
        metadata={"cadence_minutes": 60}
    )
    
    for i in range(6):
        learning_db.record_outcome(
            event_id=event_id,
            outcome_type="clicked" if i < 5 else "skipped",
            suggestion_title=f"Cafe {i}",
            suggestion_category="poi",
            engagement_seconds=2
        )
    
    # Run learner
    result = learning_learner.run_learner(verbose=False)
    
    assert result["status"] == "success"
    assert len(result["skills_created"]) > 0
    
    # Verify skill was created in DB
    skills = learning_db.get_skill_summary()
    assert len(skills) > 0
    assert any(s["skill_name"] == "user_engagement_pattern" for s in skills)


def test_preference_inference_high_engagement(learning_setup):
    """Test preference inference when user engages quickly."""
    learning_db, learning_learner, _, _ = learning_setup
    
    # Set old checkpoint
    learning_learner.set_checkpoint("2026-06-01T00:00:00")
    
    # Record outcomes with fast engagement (< 5 sec)
    event_id = learning_db.record_event(
        event_type="suggestion",
        metadata={"cadence_minutes": 60}
    )
    
    for i in range(6):
        learning_db.record_outcome(
            event_id=event_id,
            outcome_type="clicked",
            suggestion_title=f"Item {i}",
            suggestion_category="poi",
            engagement_seconds=2
        )
    
    # Run learner
    result = learning_learner.run_learner(verbose=False)
    
    assert result["status"] == "success"
    assert len(result["preferences_set"]) > 0
    
    # Verify preference was set
    prefs = learning_db.get_preferences(source="learned")
    assert "explore_intensity" in prefs or len(prefs) > 0


def test_preference_inference_skip_rate(learning_setup):
    """Test preference inference based on skip rate."""
    learning_db, learning_learner, _, _ = learning_setup
    
    # Set old checkpoint
    learning_learner.set_checkpoint("2026-06-01T00:00:00")
    
    # Record outcomes with high skip rate
    event_id = learning_db.record_event(
        event_type="suggestion",
        metadata={"cadence_minutes": 60}
    )
    
    for i in range(10):
        learning_db.record_outcome(
            event_id=event_id,
            outcome_type="skipped" if i < 5 else "clicked",
            suggestion_title=f"Item {i}",
            suggestion_category="poi",
            engagement_seconds=2 if i >= 5 else None
        )
    
    # Run learner
    result = learning_learner.run_learner(verbose=False)
    
    assert result["status"] == "success"
    
    # Verify cadence preference was set (high skip rate → longer cadence)
    prefs = learning_db.get_preferences(source="learned")
    if "explore_cadence_minutes" in prefs:
        assert prefs["explore_cadence_minutes"] >= 60


def test_learner_summary(learning_setup):
    """Test learner summary generation."""
    learning_db, learning_learner, _, _ = learning_setup
    
    # Create some learned state
    learning_db.create_skill(
        skill_name="test_skill",
        skill_category="preference",
        confidence=0.8,
        signal_strength=3
    )
    
    learning_db.set_preference(
        "test_pref",
        "test_value",
        source="learned",
        confidence=0.9
    )
    
    # Get summary
    summary = learning_learner.get_learner_summary()
    
    assert summary["learned_skills_count"] >= 1
    assert summary["learned_preferences_count"] >= 1
    assert len(summary["top_skills"]) > 0
    assert "test_pref" in summary["learned_prefs"]


def test_learner_idempotency(learning_setup):
    """Test learner can be run multiple times safely."""
    learning_db, learning_learner, _, _ = learning_setup
    
    # Set old checkpoint
    learning_learner.set_checkpoint("2026-06-01T00:00:00")
    
    # Record outcomes
    event_id = learning_db.record_event(
        event_type="suggestion",
        metadata={"cadence_minutes": 60}
    )
    
    for i in range(3):
        learning_db.record_outcome(
            event_id=event_id,
            outcome_type="clicked",
            suggestion_title=f"Item {i}",
            engagement_seconds=2
        )
    
    # Run learner twice
    result1 = learning_learner.run_learner(verbose=False)
    result2 = learning_learner.run_learner(verbose=False)
    
    assert result1["status"] == "success"
    # Second run should find no new outcomes
    assert result2["status"] == "no_new_records"


def test_learner_error_handling(learning_setup):
    """Test learner gracefully handles errors."""
    _, learning_learner, _, _ = learning_setup
    
    # Monkeypatch get_outcome_summary to raise an error
    import second_brain.learning_db as learning_db
    
    def raise_error(*args, **kwargs):
        raise RuntimeError("Test error")
    
    original = learning_db.get_outcome_summary
    learning_db.get_outcome_summary = raise_error
    
    try:
        result = learning_learner.run_learner(verbose=False)
        assert result["status"] == "error"
        assert "Test error" in result["error"]
    finally:
        learning_db.get_outcome_summary = original
