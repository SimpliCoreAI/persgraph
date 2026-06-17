"""Tests for the PersGraph Learning Worker."""
import importlib
import json
from pathlib import Path
import pytest


@pytest.fixture()
def learning_env(tmp_path, monkeypatch):
    """Set up isolated learning DB and reload modules."""
    import second_brain.learning_db as ldb
    db_path = tmp_path / "learning.db"
    monkeypatch.setattr(ldb, "DB_PATH", db_path)
    importlib.reload(ldb)
    ldb.DB_PATH = db_path

    import scripts.learning_worker as lw
    monkeypatch.setattr(lw, "learning_db", ldb)
    return ldb, lw


def _seed_outcomes(ldb, category="poi", n_accepted=5, n_skipped=2):
    from datetime import datetime, timezone, timedelta
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    outcomes = []
    for i in range(n_accepted):
        eid = ldb.record_event("suggestion", metadata={"cadence_minutes": 60})
        oid = ldb.record_outcome(eid, "accepted", suggestion_category=category)
        outcomes.append(oid)
    for i in range(n_skipped):
        eid = ldb.record_event("suggestion", metadata={"cadence_minutes": 60})
        oid = ldb.record_outcome(eid, "skipped", suggestion_category=category)
        outcomes.append(oid)
    return outcomes


def test_get_set_meta(learning_env):
    ldb, lw = learning_env
    assert ldb.get_meta("test_key") is None
    ldb.set_meta("test_key", "hello")
    assert ldb.get_meta("test_key") == "hello"


def test_cursor_roundtrip(learning_env):
    ldb, lw = learning_env
    ts = "2026-06-01T00:00:00+00:00"
    lw._set_cursor(lw.EVENT_CURSOR_KEY, ts, dry_run=False)
    assert lw._get_cursor(lw.EVENT_CURSOR_KEY) == ts


def test_dry_run_writes_nothing(learning_env):
    ldb, lw = learning_env
    _seed_outcomes(ldb)
    lw.run_learner(dry_run=True, force=True)
    # Cursor should NOT be set after dry run
    assert ldb.get_meta(lw.EVENT_CURSOR_KEY) is None
    assert ldb.get_meta(lw.OUTCOME_CURSOR_KEY) is None
    # Skills should NOT be created
    skills = ldb.get_skill_summary()
    assert len(skills) == 0


def test_category_extractor_creates_skill(learning_env):
    ldb, lw = learning_env
    _seed_outcomes(ldb, category="poi", n_accepted=5, n_skipped=2)
    outcomes = ldb.get_outcomes_since(lw.EPOCH)
    actions = lw.extract_category_preferences(outcomes, dry_run=False)
    assert any("prefers_poi" in a for a in actions)
    skills = ldb.get_skill_summary()
    assert any(s["skill_name"] == "prefers_poi" for s in skills)


def test_insufficient_signals_skipped(learning_env):
    ldb, lw = learning_env
    # Only 2 outcomes — below MIN_SIGNALS=3
    eid = ldb.record_event("suggestion", metadata={})
    ldb.record_outcome(eid, "accepted", suggestion_category="cafe")
    eid2 = ldb.record_event("suggestion", metadata={})
    ldb.record_outcome(eid2, "skipped", suggestion_category="cafe")
    outcomes = ldb.get_outcomes_since(lw.EPOCH)
    actions = lw.extract_category_preferences(outcomes, dry_run=False)
    assert len(actions) == 0


def test_idempotency(learning_env):
    ldb, lw = learning_env
    _seed_outcomes(ldb, category="poi", n_accepted=6, n_skipped=1)
    lw.run_learner(dry_run=False, force=True)
    skills_after_first = ldb.get_skill_summary()
    cursor_after_first = ldb.get_meta(lw.OUTCOME_CURSOR_KEY)

    # Second run should find no new records
    lw.run_learner(dry_run=False, force=False)
    skills_after_second = ldb.get_skill_summary()
    # Same skills, no duplicates
    assert len(skills_after_first) == len(skills_after_second)


def test_force_resets_cursor(learning_env):
    ldb, lw = learning_env
    _seed_outcomes(ldb)
    lw.run_learner(dry_run=False, force=False)
    cursor_before = ldb.get_meta(lw.OUTCOME_CURSOR_KEY)
    assert cursor_before != lw.EPOCH

    # Force reprocesses from start
    lw.run_learner(dry_run=False, force=True)
    # After force run the cursor is reset then advanced again
    cursor_after = ldb.get_meta(lw.OUTCOME_CURSOR_KEY)
    assert cursor_after is not None


def test_command_pattern_skill(learning_env):
    ldb, lw = learning_env
    for _ in range(4):
        ldb.record_event("command_usage", metadata={"command": "/note"})
    events = ldb.get_events_since(lw.EPOCH)
    actions = lw.extract_command_patterns(events, dry_run=False)
    assert any("frequent_note_user" in a for a in actions)


def test_empty_db_no_op(learning_env):
    ldb, lw = learning_env
    # Should exit cleanly with nothing to process
    lw.run_learner(dry_run=False, force=False)
    assert ldb.get_meta(lw.LAST_RUN_KEY) is not None
