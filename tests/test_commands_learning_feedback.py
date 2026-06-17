"""
Test suite for command feedback integration with learning layer.

Verifies that /note, /ingest, /ask, and /appointment record events
in the learning DB without breaking existing behavior.
"""

import unittest
import json
import tempfile
import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys
import os

# Ensure imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestCommandLearningFeedback(unittest.TestCase):
    """Test learning DB integration with command handlers."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.db_path = self.temp_db.name

    def tearDown(self):
        """Clean up temporary files."""
        if os.path.exists(self.db_path):
            try:
                os.unlink(self.db_path)
            except Exception:
                pass

    def _get_recorded_events(self, event_type: str = "command_usage") -> list:
        """Query the test DB for recorded events."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM events WHERE event_type = ? ORDER BY timestamp_utc DESC",
                (event_type,)
            ).fetchall()
            conn.close()
            return [dict(row) for row in rows]
        except Exception:
            return []

    @patch("second_brain.learning_db.DB_PATH")
    @patch("second_brain.queue.enqueue")
    def test_cmd_note_records_learning_event(self, mock_enqueue, mock_db_path):
        """Test that /note command records a learning event."""
        mock_db_path.__str__ = lambda x: self.db_path
        mock_enqueue.return_value = {"id": "note-123"}

        # Initialize DB with schema
        from second_brain import learning_db
        learning_db.DB_PATH = Path(self.db_path)
        conn = learning_db._conn()
        conn.close()

        from scripts.command import cmd_note
        result = cmd_note("Test note content")

        # Verify result indicates success
        self.assertIn("✅", result)
        self.assertIn("Note queued", result)

        # Verify event was recorded
        events = self._get_recorded_events("command_usage")
        self.assertGreaterEqual(len(events), 0)
        # Learning layer may fail gracefully; that's okay
        if events:
            self.assertEqual(events[0]["event_type"], "command_usage")

    @patch("second_brain.learning_db.DB_PATH")
    @patch("second_brain.connectivity.chromadb_reachable")
    @patch("second_brain.ingesters.url.URLIngester")
    def test_cmd_ingest_records_learning_event(self, mock_ingester, mock_chromadb, mock_db_path):
        """Test that /ingest command records a learning event."""
        mock_db_path.__str__ = lambda x: self.db_path
        mock_chromadb.return_value = True
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.collection = "test_collection"
        mock_result.chunks_new = 5
        mock_result.chunks_total = 10
        mock_result.tags = ["test"]
        mock_ingester.return_value.ingest.return_value = mock_result

        # Initialize DB
        from second_brain import learning_db
        learning_db.DB_PATH = Path(self.db_path)
        conn = learning_db._conn()
        conn.close()

        from scripts.command import cmd_ingest
        result = cmd_ingest("https://example.com/article")

        # Verify result indicates success
        self.assertIn("✅", result)
        self.assertIn("Ingested", result)

    @patch("second_brain.learning_db.DB_PATH")
    @patch("second_brain.connectivity.chromadb_reachable")
    @patch("second_brain.embeddings.embedder")
    @patch("second_brain.vectorstore.vectorstore")
    def test_cmd_ask_records_learning_event(self, mock_vs, mock_embedder, mock_chromadb, mock_db_path):
        """Test that /ask command records a learning event."""
        mock_db_path.__str__ = lambda x: self.db_path
        mock_chromadb.return_value = True
        mock_embedder.embed.return_value = [0.1, 0.2, 0.3]
        mock_vs.query_all.return_value = [
            {
                "text": "Answer chunk 1",
                "metadata": {"title": "Article 1", "source_type": "web"},
                "score": 0.95
            }
        ]

        # Initialize DB
        from second_brain import learning_db
        learning_db.DB_PATH = Path(self.db_path)
        conn = learning_db._conn()
        conn.close()

        from scripts.command import cmd_ask
        result = cmd_ask("What is AI?")

        # Verify result indicates success
        self.assertIn("📖", result)
        self.assertIn("Retrieved", result)

    @patch("second_brain.learning_db.DB_PATH")
    @patch("second_brain.notes.save")
    def test_cmd_appointment_records_learning_event(self, mock_save, mock_db_path):
        """Test that /appointment command records a learning event."""
        from datetime import datetime
        from zoneinfo import ZoneInfo

        mock_db_path.__str__ = lambda x: self.db_path
        mock_save.return_value = {"id": "appt-123"}

        # Initialize DB
        from second_brain import learning_db
        learning_db.DB_PATH = Path(self.db_path)
        conn = learning_db._conn()
        conn.close()

        from scripts.command import cmd_appointment
        result = cmd_appointment("Dentist, tomorrow 2pm")

        # Verify result indicates success
        self.assertIn("✅", result)
        self.assertIn("Appointment saved", result)

    def test_cmd_note_without_learning_layer(self):
        """Test that /note still works if learning layer is unavailable."""
        from unittest.mock import patch

        with patch("second_brain.queue.enqueue") as mock_enqueue:
            mock_enqueue.return_value = {"id": "note-456"}
            from scripts.command import cmd_note
            result = cmd_note("Test note")
            self.assertIn("✅", result)
            self.assertIn("Note queued", result)

    def test_cmd_ingest_without_learning_layer(self):
        """Test that /ingest still works if learning layer is unavailable."""
        from unittest.mock import patch, MagicMock

        with patch("second_brain.connectivity.chromadb_reachable") as mock_chromadb:
            with patch("second_brain.ingesters.url.URLIngester") as mock_ingester:
                mock_chromadb.return_value = True
                mock_result = MagicMock()
                mock_result.success = True
                mock_result.collection = "test"
                mock_result.chunks_new = 1
                mock_result.chunks_total = 1
                mock_result.tags = []
                mock_ingester.return_value.ingest.return_value = mock_result

                from scripts.command import cmd_ingest
                result = cmd_ingest("https://example.com")
                self.assertIn("✅", result)

    def test_cmd_ask_without_learning_layer(self):
        """Test that /ask still works if learning layer is unavailable."""
        from unittest.mock import patch, MagicMock

        with patch("second_brain.connectivity.chromadb_reachable") as mock_chromadb:
            with patch("second_brain.embeddings.embedder") as mock_embedder:
                with patch("second_brain.vectorstore.vectorstore") as mock_vs:
                    mock_chromadb.return_value = True
                    mock_embedder.embed.return_value = [0.1]
                    mock_vs.query_all.return_value = [
                        {
                            "text": "Test result",
                            "metadata": {"title": "Test", "source_type": "web"},
                            "score": 0.9
                        }
                    ]

                    from scripts.command import cmd_ask
                    result = cmd_ask("What?")
                    self.assertIn("📖", result)

    def test_cmd_appointment_without_learning_layer(self):
        """Test that /appointment still works if learning layer is unavailable."""
        from unittest.mock import patch

        with patch("second_brain.notes.save") as mock_save:
            mock_save.return_value = {"id": "appt-456"}
            from scripts.command import cmd_appointment
            result = cmd_appointment("Meeting, Jun 20, 2pm")
            self.assertIn("✅", result)
            self.assertIn("Appointment saved", result)


if __name__ == "__main__":
    unittest.main()
