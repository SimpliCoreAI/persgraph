"""
Tests for the universal feedback wrapper in command.py.
Verifies that _attach_feedback_id() emits event IDs for all
meaningful commands and correctly excludes /pghelp, /status,
short responses, and already-ID'd responses.
"""
from __future__ import annotations
import importlib
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


MOCK_USER = {"id": "8596241969", "tier": "owner", "name": "test"}
FAKE_EVENT_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def _make_ldb_mock():
    """Return a mock learning_db that captures record_event calls."""
    m = MagicMock()
    m.record_event.return_value = FAKE_EVENT_ID
    return m


# ---------------------------------------------------------------------------
# Direct unit tests on _attach_feedback_id
# ---------------------------------------------------------------------------

def test_wrapper_attaches_id_to_task():
    from scripts.command import _attach_feedback_id
    with patch("scripts.command.learning_db") as mock_ldb:
        mock_ldb.record_event.return_value = FAKE_EVENT_ID
        result = _attach_feedback_id("Task saved.", "/task", "/task buy milk", MOCK_USER)
    assert "🆔 Event ID" in result
    assert FAKE_EVENT_ID in result


def test_wrapper_attaches_id_to_place():
    from scripts.command import _attach_feedback_id
    with patch("scripts.command.learning_db") as mock_ldb:
        mock_ldb.record_event.return_value = FAKE_EVENT_ID
        result = _attach_feedback_id("Place saved.", "/place", "/place Blue Bottle, SF", MOCK_USER)
    assert "🆔 Event ID" in result


def test_wrapper_attaches_id_to_sport():
    from scripts.command import _attach_feedback_id
    with patch("scripts.command.learning_db") as mock_ldb:
        mock_ldb.record_event.return_value = FAKE_EVENT_ID
        result = _attach_feedback_id("NBA scores...", "/sport", "/sport nba", MOCK_USER)
    assert "🆔 Event ID" in result


def test_wrapper_attaches_id_to_schedule():
    from scripts.command import _attach_feedback_id
    with patch("scripts.command.learning_db") as mock_ldb:
        mock_ldb.record_event.return_value = FAKE_EVENT_ID
        result = _attach_feedback_id("Schedule: ...", "/schedule", "/schedule week", MOCK_USER)
    assert "🆔 Event ID" in result


def test_wrapper_skips_pghelp():
    from scripts.command import _attach_feedback_id
    with patch("scripts.command.learning_db") as mock_ldb:
        mock_ldb.record_event.return_value = FAKE_EVENT_ID
        result = _attach_feedback_id("PersGraph help text...", "/pghelp", "/pghelp", MOCK_USER)
    assert "🆔 Event ID" not in result
    mock_ldb.record_event.assert_not_called()


def test_wrapper_skips_status():
    from scripts.command import _attach_feedback_id
    with patch("scripts.command.learning_db") as mock_ldb:
        mock_ldb.record_event.return_value = FAKE_EVENT_ID
        result = _attach_feedback_id("Status: OK...", "/status", "/status", MOCK_USER)
    assert "🆔 Event ID" not in result
    mock_ldb.record_event.assert_not_called()


def test_wrapper_skips_short_response():
    from scripts.command import _attach_feedback_id
    with patch("scripts.command.learning_db") as mock_ldb:
        mock_ldb.record_event.return_value = FAKE_EVENT_ID
        result = _attach_feedback_id("err", "/task", "/task", MOCK_USER)
    assert "🆔 Event ID" not in result


def test_wrapper_no_duplicate_id():
    from scripts.command import _attach_feedback_id
    existing = "Result.\n\n🆔 Event ID: `existing-id-already`"
    with patch("scripts.command.learning_db") as mock_ldb:
        mock_ldb.record_event.return_value = FAKE_EVENT_ID
        result = _attach_feedback_id(existing, "/ask", "/ask something", MOCK_USER)
    assert result.count("🆔 Event ID") == 1
    assert "existing-id-already" in result
    mock_ldb.record_event.assert_not_called()


def test_wrapper_safe_on_exception():
    from scripts.command import _attach_feedback_id
    with patch("scripts.command.learning_db") as mock_ldb:
        mock_ldb.record_event.side_effect = RuntimeError("DB exploded")
        result = _attach_feedback_id("Safe response here", "/task", "/task x", MOCK_USER)
    # Original response returned intact even on DB failure
    assert "Safe response here" in result


def test_wrapper_stores_correct_metadata():
    from scripts.command import _attach_feedback_id, _REQUEST_TYPE_MAP
    captured = {}
    def fake_record(event_type, metadata=None, **kwargs):
        captured.update(metadata or {})
        return FAKE_EVENT_ID
    with patch("scripts.command.learning_db") as mock_ldb:
        mock_ldb.record_event.side_effect = fake_record
        _attach_feedback_id("Some long enough response text", "/ask", "/ask something detailed", MOCK_USER)
    assert captured.get("command") == "/ask"
    assert captured.get("request_type") == "developer_query"
    assert captured.get("user_tier") == "owner"
