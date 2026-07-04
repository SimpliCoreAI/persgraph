import json
import importlib
from pathlib import Path

import pytest


@pytest.fixture()
def learning_modules(tmp_path, monkeypatch):
    import second_brain.learning_db as learning_db
    import second_brain.learning_explore_integration as learning_integration

    db_path = tmp_path / "learning.db"
    monkeypatch.setattr(learning_db, "DB_PATH", db_path)
    importlib.reload(learning_db)
    importlib.reload(learning_integration)
    monkeypatch.setattr(learning_integration, "LEARNING_AVAILABLE", True)
    learning_db.DB_PATH = db_path
    return learning_db, learning_integration, db_path


def test_record_event_and_outcome_roundtrip(learning_modules):
    learning_db, _, db_path = learning_modules

    event_id = learning_db.record_event(
        event_type="suggestion",
        explore_session_id="sess-1",
        location={"lat": 37.0, "lon": -122.0, "accuracy_m": 15},
        metadata={"cadence_minutes": 60, "intensity": "medium"},
    )
    assert event_id
    assert learning_db.DB_PATH.exists()

    outcome_id = learning_db.record_outcome(
        event_id=event_id,
        outcome_type="clicked",
        suggestion_title="Port Costa",
        suggestion_category="poi",
        engagement_seconds=12,
        feedback="nice",
    )
    assert outcome_id

    events = learning_db.get_event_summary(limit=10)
    outcomes = learning_db.get_outcome_summary(limit=10)

    assert len(events) == 1
    assert events[0]["event_type"] == "suggestion"
    assert events[0]["session_id"] == "sess-1"
    assert events[0]["metadata"]["cadence_minutes"] == 60

    assert len(outcomes) == 1
    assert outcomes[0]["outcome_type"] == "clicked"
    assert outcomes[0]["suggestion_title"] == "Port Costa"


def test_preferences_and_skills_helpers(learning_modules):
    learning_db, _, _ = learning_modules

    learning_db.set_preference(
        "explore_cadence_minutes",
        60,
        source="learned",
        confidence=0.9,
    )
    pref = learning_db.get_preferences()
    assert pref["explore_cadence_minutes"] == 60

    skill_id = learning_db.create_skill(
        skill_name="prefers_good_rated_cafes",
        skill_category="preference",
        confidence=0.7,
        signal_strength=3,
        skill_data={"min_rating": 4.0},
    )
    assert skill_id
    skills = learning_db.get_skill_summary()
    assert any(s["skill_name"] == "prefers_good_rated_cafes" for s in skills)


def test_skip_event_records(learning_modules):
    learning_db, _, _ = learning_modules
    event_id = learning_db.record_skip(
        explore_session_id="sess-2",
        reason="cadence_window_not_reached",
        location={"lat": 1.0, "lon": 2.0},
    )
    assert event_id
    counts = learning_db.count_events_by_type()
    assert counts["skip"] >= 1


def test_explore_integration_hooks(monkeypatch, learning_modules):
    _, learning_integration, _ = learning_modules

    calls = {}

    def fake_set_preference(key, value, source="manual", confidence=1.0):
        calls["pref"] = (key, value, source, confidence)

    def fake_record_event(event_type, explore_session_id=None, location=None, metadata=None):
        calls.setdefault("events", []).append((event_type, explore_session_id, location, metadata))
        return "evt-1"

    def fake_record_skip(explore_session_id=None, reason=None, location=None):
        calls.setdefault("skips", []).append((explore_session_id, reason, location))
        return "skip-1"

    def fake_record_outcome(**kwargs):
        calls.setdefault("outcomes", []).append(kwargs)
        return "out-1"

    monkeypatch.setattr(learning_integration, "set_preference", fake_set_preference)
    monkeypatch.setattr(learning_integration, "record_event", fake_record_event)
    monkeypatch.setattr(learning_integration, "record_skip", fake_record_skip)
    monkeypatch.setattr(learning_integration, "record_outcome", fake_record_outcome)

    session_id = learning_integration.on_explore_enabled("2h", 60, "medium", {"lat": 1})
    assert session_id
    assert calls["pref"][0].startswith("explore_session_")

    event_id = learning_integration.on_suggestion_offered(
        "Cafe",
        "poi",
        60,
        "medium",
        {"lat": 1},
        session_id,
    )
    assert event_id == "evt-1"

    skip_id = learning_integration.on_skip_event("cadence_window_not_reached", session_id, {"lat": 1})
    assert skip_id == "skip-1"

    outcome_id = learning_integration.on_suggestion_clicked("evt-1", "Cafe", "poi", 10)
    assert outcome_id == "out-1"
    assert calls["outcomes"][0]["outcome_type"] == "clicked"


def test_format_suggestion_message_strips_bucketlist_noise():
    from scripts.explore_mode import ExploreSuggestion, format_suggestion_message

    suggestion = ExploreSuggestion(
        title="Port Costa [saved in bucket-list]",
        reason="popular • 0.0 km • California 🗺 https://maps.example",
        meal="📍 BucketList",
        tag="poi",
    )
    msg = format_suggestion_message(suggestion, {"cadence_minutes": 30})
    assert "saved in bucket-list" not in msg
    assert "📍 BucketList" not in msg
    assert "⏱ Next check" in msg and "30m" in msg
