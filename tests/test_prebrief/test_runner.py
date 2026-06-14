"""
Tests for Prebrief Runner module (Batch 7).

Tests cover:
- PrebriefConfig: environment loading, credential detection
- PrebriefRunner: source loading, dry-run mode, output writing
- Source filtering: calendar, gmail, yahoo, mixed, all
- Partial failure handling: one source fails, others continue
- Output directory creation
- JSON and Markdown output files
- Dry-run fixture mode (no live network)
- Config and credential handling
"""

import json
import os
import tempfile
from datetime import date
from pathlib import Path
from unittest import mock

import pytest

# Import modules under test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.run_prebrief import PrebriefConfig, PrebriefRunner
from second_brain.connectors.schemas import CalendarEvent, InboxEmail


class TestPrebriefConfig:
    """Tests for PrebriefConfig."""

    def test_config_initializes_with_dry_run_false(self):
        """Config should initialize with dry_run=False by default."""
        config = PrebriefConfig(dry_run=False)
        assert config.dry_run is False
        assert config.output_dir == Path("data")

    def test_config_initializes_with_dry_run_true(self):
        """Config should initialize with dry_run=True."""
        config = PrebriefConfig(dry_run=True)
        assert config.dry_run is True

    def test_config_reference_date_defaults_to_today(self):
        """Config reference_date should default to today."""
        config = PrebriefConfig()
        assert config.reference_date == date.today()

    def test_config_gmail_credentials_missing(self):
        """Config should return None for gmail_username when not set."""
        with mock.patch.dict(os.environ, {}, clear=True):
            config = PrebriefConfig()
            assert config.gmail_username is None
            assert config.gmail_password is None

    def test_config_gmail_credentials_present(self):
        """Config should return gmail credentials when set."""
        with mock.patch.dict(
            os.environ,
            {
                "GMAIL_IMAP_USERNAME": "test@gmail.com",
                "GMAIL_IMAP_APP_PASSWORD": "app-password-123",
            },
        ):
            config = PrebriefConfig()
            assert config.gmail_username == "test@gmail.com"
            assert config.gmail_password == "app-password-123"

    def test_config_has_gmail_credentials_true(self):
        """has_gmail_credentials should return True when both set."""
        with mock.patch.dict(
            os.environ,
            {
                "GMAIL_IMAP_USERNAME": "test@gmail.com",
                "GMAIL_IMAP_APP_PASSWORD": "password",
            },
        ):
            config = PrebriefConfig()
            assert config.has_gmail_credentials() is True

    def test_config_has_gmail_credentials_false(self):
        """has_gmail_credentials should return False when missing."""
        with mock.patch.dict(os.environ, {}, clear=True):
            config = PrebriefConfig()
            assert config.has_gmail_credentials() is False

    def test_config_has_yahoo_credentials_true(self):
        """has_yahoo_credentials should return True when both set."""
        with mock.patch.dict(
            os.environ,
            {
                "YAHOO_IMAP_USERNAME": "test@yahoo.com",
                "YAHOO_IMAP_APP_PASSWORD": "password",
            },
        ):
            config = PrebriefConfig()
            assert config.has_yahoo_credentials() is True

    def test_config_has_yahoo_credentials_false(self):
        """has_yahoo_credentials should return False when missing."""
        with mock.patch.dict(os.environ, {}, clear=True):
            config = PrebriefConfig()
            assert config.has_yahoo_credentials() is False


class TestPrebriefRunnerDryRun:
    """Tests for PrebriefRunner in dry-run mode."""

    def test_runner_dry_run_with_calendar(self):
        """Runner should load synthetic calendar in dry-run mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = PrebriefConfig(dry_run=True)
            config.output_dir = Path(tmpdir)
            runner = PrebriefRunner(config, sources=["calendar"])
            result = runner.run()

            assert result["success"] is True
            assert len(result["events"]) == 3  # events.json has 3
            assert len(result["emails"]) == 0

    def test_runner_dry_run_with_gmail(self):
        """Runner should load synthetic Gmail in dry-run mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = PrebriefConfig(dry_run=True)
            config.output_dir = Path(tmpdir)
            runner = PrebriefRunner(config, sources=["gmail"])
            result = runner.run()

            assert result["success"] is True
            assert len(result["events"]) == 0
            assert len(result["emails"]) == 4  # emails.json has 4

    def test_runner_dry_run_with_yahoo(self):
        """Runner should load synthetic Yahoo in dry-run mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = PrebriefConfig(dry_run=True)
            config.output_dir = Path(tmpdir)
            runner = PrebriefRunner(config, sources=["yahoo"])
            result = runner.run()

            assert result["success"] is True
            assert len(result["events"]) == 0
            assert len(result["emails"]) == 4  # emails.json has 4
            # Yahoo emails should have source="yahoo"
            if result["emails"]:
                assert result["emails"][0]["source"] == "yahoo"

    def test_runner_dry_run_all_sources(self):
        """Runner should load all sources in dry-run mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = PrebriefConfig(dry_run=True)
            config.output_dir = Path(tmpdir)
            runner = PrebriefRunner(config, sources=["calendar", "gmail", "yahoo"])
            result = runner.run()

            assert result["success"] is True
            assert len(result["events"]) == 3  # from calendar fixture
            assert len(result["emails"]) == 8  # 4 from gmail + 4 from yahoo

    def test_runner_dry_run_default_sources(self):
        """Runner should use default sources (calendar, gmail) if not specified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = PrebriefConfig(dry_run=True)
            config.output_dir = Path(tmpdir)
            runner = PrebriefRunner(config)  # no sources specified
            result = runner.run()

            assert result["success"] is True
            assert len(result["events"]) == 3  # from calendar fixture
            assert len(result["emails"]) == 4  # from gmail only


class TestPrebriefRunnerOutputs:
    """Tests for PrebriefRunner output file writing."""

    def test_runner_creates_output_directory(self):
        """Runner should create output directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "prebrief_output"
            assert not output_dir.exists()

            config = PrebriefConfig(dry_run=True)
            config.output_dir = output_dir
            runner = PrebriefRunner(config, sources=["calendar"])
            result = runner.run()

            assert output_dir.exists()

    def test_runner_writes_json_file(self):
        """Runner should write prebrief_context.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = PrebriefConfig(dry_run=True)
            config.output_dir = Path(tmpdir)
            runner = PrebriefRunner(config, sources=["calendar"])
            result = runner.run()

            json_file = Path(tmpdir) / "prebrief_context.json"
            assert json_file.exists()

            # Verify JSON is valid
            with open(json_file) as f:
                data = json.load(f)
            assert "date" in data
            assert "generated_at" in data
            assert "events_today" in data

    def test_runner_writes_markdown_file(self):
        """Runner should write prebrief_context.md."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = PrebriefConfig(dry_run=True)
            config.output_dir = Path(tmpdir)
            runner = PrebriefRunner(config, sources=["calendar"])
            result = runner.run()

            md_file = Path(tmpdir) / "prebrief_context.md"
            assert md_file.exists()

            # Verify Markdown is valid
            with open(md_file) as f:
                content = f.read()
            assert "# Daily Prebrief" in content
            assert "## " in content  # Section headers

    def test_runner_json_output_is_valid_schema(self):
        """JSON output should match DailyContext schema."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = PrebriefConfig(dry_run=True)
            config.output_dir = Path(tmpdir)
            runner = PrebriefRunner(config, sources=["calendar", "gmail"])
            result = runner.run()

            json_file = Path(tmpdir) / "prebrief_context.json"
            with open(json_file) as f:
                data = json.load(f)

            # Check required fields
            assert "date" in data
            assert "generated_at" in data
            assert "events_today" in data
            assert "events_upcoming" in data
            assert "bills_due" in data
            assert "followups_needed" in data
            assert "worth_checking" in data
            assert "carry_forward" in data
            assert "suggested_priorities" in data

            # Check section structure
            for section_key in [
                "events_today",
                "events_upcoming",
                "bills_due",
                "followups_needed",
                "worth_checking",
                "carry_forward",
            ]:
                section = data[section_key]
                assert "items" in section
                assert "capped" in section
                assert "cap_limit" in section


class TestPrebriefRunnerPartialFailure:
    """Tests for partial failure handling."""

    def test_runner_handles_unknown_source(self):
        """Runner should warn and continue for unknown sources."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = PrebriefConfig(dry_run=True)
            config.output_dir = Path(tmpdir)
            runner = PrebriefRunner(config, sources=["unknown_source"])
            result = runner.run()

            # Should fail because no valid sources produced data
            assert result["success"] is False
            assert "unknown_source" in runner.sources

    def test_runner_empty_sources_uses_defaults(self):
        """Runner should use default sources when empty list passed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = PrebriefConfig(dry_run=True)
            config.output_dir = Path(tmpdir)
            runner = PrebriefRunner(config, sources=[])  # Empty list
            # Empty list is falsy, so defaults to ["calendar", "gmail"]
            assert runner.sources == ["calendar", "gmail"]
            result = runner.run()
            # Should succeed with defaults
            assert result["success"] is True

    def test_runner_partial_failure_gmail_missing_credentials(self):
        """Runner should skip Gmail if credentials missing in live mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.dict(os.environ, {}, clear=True):
                config = PrebriefConfig(dry_run=False)
                config.output_dir = Path(tmpdir)
                runner = PrebriefRunner(config, sources=["calendar", "gmail"])
                result = runner.run()

                # Should fail because calendar not yet implemented
                # and Gmail credentials missing
                assert result["success"] is False

    def test_runner_errors_dict_populated_on_failure(self):
        """Runner should populate errors dict with source failures."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = PrebriefConfig(dry_run=False)
            config.output_dir = Path(tmpdir)
            with mock.patch.dict(os.environ, {}, clear=True):
                runner = PrebriefRunner(config, sources=["gmail"])
                result = runner.run()

                assert result["success"] is False
                assert len(result["errors"]) > 0


class TestPrebriefRunnerSourceFiltering:
    """Tests for source filtering."""

    def test_runner_filters_to_calendar_only(self):
        """Runner should load only calendar when specified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = PrebriefConfig(dry_run=True)
            config.output_dir = Path(tmpdir)
            runner = PrebriefRunner(config, sources=["calendar"])

            assert "calendar" in runner.sources
            assert "gmail" not in runner.sources
            assert "yahoo" not in runner.sources

    def test_runner_filters_to_gmail_only(self):
        """Runner should load only Gmail when specified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = PrebriefConfig(dry_run=True)
            config.output_dir = Path(tmpdir)
            runner = PrebriefRunner(config, sources=["gmail"])

            assert "gmail" in runner.sources
            assert "calendar" not in runner.sources
            assert "yahoo" not in runner.sources

    def test_runner_filters_to_yahoo_only(self):
        """Runner should load only Yahoo when specified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = PrebriefConfig(dry_run=True)
            config.output_dir = Path(tmpdir)
            runner = PrebriefRunner(config, sources=["yahoo"])

            assert "yahoo" in runner.sources
            assert "calendar" not in runner.sources
            assert "gmail" not in runner.sources

    def test_runner_filters_to_calendar_gmail(self):
        """Runner should load calendar + Gmail when specified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = PrebriefConfig(dry_run=True)
            config.output_dir = Path(tmpdir)
            runner = PrebriefRunner(config, sources=["calendar", "gmail"])
            result = runner.run()

            assert result["success"] is True
            assert len(result["events"]) == 3  # from calendar fixture
            assert len(result["emails"]) == 4  # from gmail

    def test_runner_filters_to_calendar_yahoo(self):
        """Runner should load calendar + Yahoo when specified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = PrebriefConfig(dry_run=True)
            config.output_dir = Path(tmpdir)
            runner = PrebriefRunner(config, sources=["calendar", "yahoo"])
            result = runner.run()

            assert result["success"] is True
            assert len(result["events"]) == 3  # from calendar fixture
            assert len(result["emails"]) == 4  # from yahoo


class TestPrebriefRunnerIntegration:
    """Integration tests for complete workflow."""

    def test_runner_full_dry_run_workflow(self):
        """Test complete dry-run workflow from config to output files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = PrebriefConfig(dry_run=True)
            config.output_dir = Path(tmpdir)
            runner = PrebriefRunner(config, sources=["calendar", "gmail"])
            result = runner.run()

            # Success
            assert result["success"] is True

            # Events and emails loaded
            assert len(result["events"]) == 3
            assert len(result["emails"]) == 4

            # Output files written
            json_file = Path(tmpdir) / "prebrief_context.json"
            md_file = Path(tmpdir) / "prebrief_context.md"
            assert json_file.exists()
            assert md_file.exists()

            # Context structure
            context = result["context"]
            assert context["date"] == date.today().isoformat()
            assert len(context["events_today"]["items"]) >= 0
            assert len(context["events_upcoming"]["items"]) >= 0

    def test_runner_result_includes_metadata(self):
        """Result dict should include all metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = PrebriefConfig(dry_run=True)
            config.output_dir = Path(tmpdir)
            runner = PrebriefRunner(config, sources=["calendar"])
            result = runner.run()

            assert "success" in result
            assert "context" in result
            assert "events" in result
            assert "emails" in result
            assert "sources" in result
            assert "errors" in result

    def test_runner_result_sources_list_successful(self):
        """Result sources should list only successful sources."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = PrebriefConfig(dry_run=True)
            config.output_dir = Path(tmpdir)
            runner = PrebriefRunner(config, sources=["calendar", "gmail"])
            result = runner.run()

            assert "calendar" in result["sources"]
            assert "gmail" in result["sources"]

    def test_runner_gmail_source_overridden_to_gmail(self):
        """Gmail emails should have source='gmail' in dry-run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = PrebriefConfig(dry_run=True)
            config.output_dir = Path(tmpdir)
            runner = PrebriefRunner(config, sources=["gmail"])
            result = runner.run()

            for email in result["emails"]:
                assert email["source"] == "gmail"

    def test_runner_yahoo_source_preserved(self):
        """Yahoo emails should have source='yahoo' in dry-run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = PrebriefConfig(dry_run=True)
            config.output_dir = Path(tmpdir)
            runner = PrebriefRunner(config, sources=["yahoo"])
            result = runner.run()

            for email in result["emails"]:
                assert email["source"] == "yahoo"

    def test_runner_events_have_calendar_source(self):
        """Calendar events should have source field."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = PrebriefConfig(dry_run=True)
            config.output_dir = Path(tmpdir)
            runner = PrebriefRunner(config, sources=["calendar"])
            result = runner.run()

            for event in result["events"]:
                assert "source" in event

    def test_runner_builds_valid_daily_context(self):
        """Runner should build valid DailyContext."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = PrebriefConfig(dry_run=True)
            config.output_dir = Path(tmpdir)
            runner = PrebriefRunner(config, sources=["calendar", "gmail"])
            result = runner.run()

            context = result["context"]
            # Check all sections are present
            for section in [
                "events_today",
                "events_upcoming",
                "bills_due",
                "followups_needed",
                "worth_checking",
                "carry_forward",
            ]:
                assert section in context
                assert "items" in context[section]
                assert isinstance(context[section]["items"], list)

    def test_runner_suggested_priorities_generated(self):
        """Runner should generate suggested priorities."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = PrebriefConfig(dry_run=True)
            config.output_dir = Path(tmpdir)
            runner = PrebriefRunner(config, sources=["calendar", "gmail"])
            result = runner.run()

            context = result["context"]
            assert "suggested_priorities" in context
            assert isinstance(context["suggested_priorities"], list)


class TestPrebriefRunnerConfigLoading:
    """Tests for configuration loading."""

    def test_config_loads_from_env(self):
        """Config should load from environment variables."""
        with mock.patch.dict(
            os.environ,
            {
                "GMAIL_IMAP_USERNAME": "test@gmail.com",
                "GMAIL_IMAP_APP_PASSWORD": "app-pass",
            },
        ):
            config = PrebriefConfig(dry_run=True)
            assert config.has_gmail_credentials() is True

    def test_runner_respects_reference_date(self):
        """Runner should use config reference_date in builder."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_date = date(2026, 6, 15)
            config = PrebriefConfig(dry_run=True)
            config.reference_date = test_date
            config.output_dir = Path(tmpdir)

            runner = PrebriefRunner(config, sources=["calendar"])
            result = runner.run()

            context = result["context"]
            assert context["date"] == test_date.isoformat()


class TestPrebriefRunnerEdgeCases:
    """Edge case tests."""

    def test_runner_with_empty_events_and_valid_emails(self):
        """Runner should succeed with emails but no events."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = PrebriefConfig(dry_run=True)
            config.output_dir = Path(tmpdir)
            runner = PrebriefRunner(config, sources=["gmail"])
            result = runner.run()

            assert result["success"] is True
            assert len(result["events"]) == 0
            assert len(result["emails"]) > 0

    def test_runner_with_empty_emails_and_valid_events(self):
        """Runner should succeed with events but no emails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = PrebriefConfig(dry_run=True)
            config.output_dir = Path(tmpdir)
            runner = PrebriefRunner(config, sources=["calendar"])
            result = runner.run()

            assert result["success"] is True
            assert len(result["events"]) > 0
            assert len(result["emails"]) == 0
