"""Tests for Learning Digest section in weekly_briefing.py."""
import importlib
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


def _make_skill(name, confidence):
    return {"skill_name": name, "category": "preference", "confidence": confidence, "signal_strength": 3, "skill_data": {}}


def test_learning_digest_with_data():
    """Briefing compose includes skills and learned prefs when data exists."""
    from scripts.weekly_briefing import compose
    from second_brain.briefing_state import BriefingStateManager, BriefingStep

    state_mgr = MagicMock()
    state_mgr.transition = MagicMock()

    collected = {
        "tasks": [],
        "appointments": [],
        "api_costs": {},
        "explore_feedback": {"outcome_counts": {}, "recent_outcomes": []},
        "learning_digest": {
            "skills": [_make_skill("prefers_poi", 0.82), _make_skill("frequent_note_user", 0.60)],
            "learned_prefs": {"explore_cadence_minutes": 45},
        },
        "system_health": {"disk_usage": "10%"},
    }

    result = compose(state_mgr, collected, week_number=25)
    assert "Learning Digest" in result
    assert "prefers_poi" in result
    assert "explore_cadence_minutes" in result


def test_learning_digest_empty_graceful():
    """Briefing compose handles empty learning digest gracefully."""
    from scripts.weekly_briefing import compose
    from second_brain.briefing_state import BriefingStateManager, BriefingStep

    state_mgr = MagicMock()
    state_mgr.transition = MagicMock()

    collected = {
        "tasks": [],
        "appointments": [],
        "api_costs": {},
        "explore_feedback": {"outcome_counts": {}, "recent_outcomes": []},
        "learning_digest": {"skills": [], "learned_prefs": {}},
        "system_health": {},
    }

    result = compose(state_mgr, collected, week_number=25)
    assert "Learning Digest" in result
    assert "No learned skills yet" in result


def test_learning_digest_error_graceful():
    """Briefing compose handles learning digest error gracefully."""
    from scripts.weekly_briefing import compose

    state_mgr = MagicMock()
    state_mgr.transition = MagicMock()

    collected = {
        "tasks": [],
        "appointments": [],
        "api_costs": {},
        "explore_feedback": {"outcome_counts": {}, "recent_outcomes": []},
        "learning_digest": {"error": "DB unavailable"},
        "system_health": {},
    }

    result = compose(state_mgr, collected, week_number=25)
    assert "Learning Digest" in result
    assert "unavailable" in result
