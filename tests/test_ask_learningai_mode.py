from unittest.mock import patch
from scripts.command import cmd_ask


def test_ask_learningai_mode_emits_prep_answer():
    with patch('second_brain.learning_db.record_event', return_value='11111111-2222-3333-4444-555555555555'):
        out = cmd_ask('learningai langgraph interview loops')
    assert 'LearningAI prep mode for: langgraph interview loops' in out
    assert 'Event ID' in out


def test_ask_prep_mode_works():
    with patch('second_brain.learning_db.record_event', return_value='11111111-2222-3333-4444-555555555555'):
        out = cmd_ask('prep rag tradeoffs')
    assert 'LearningAI prep mode for: rag tradeoffs' in out


def test_plain_ask_path_unchanged_requires_kb():
    with patch('second_brain.connectivity.chromadb_reachable', return_value=False):
        out = cmd_ask('what is rag?')
    assert "Can't reach the knowledge base" in out
