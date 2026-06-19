#!/usr/bin/env python3
"""
Prebrief Runner for Batch 7.

Entry point for building daily prebrief context from calendar + email sources.
Orchestrates: config loading, source selection, normalization, building, and output writing.

Supports:
- Dry-run fixture mode (--dry-run): uses synthetic fixtures instead of live sources
- Source filtering: --sources calendar,gmail,yahoo (or 'all' for all sources)
- Output directory creation (auto-creates data/ if missing)
- Partial failure handling: one source failing doesn't abort the whole run
- Machine-readable output: data/prebrief_context.json
- Human-readable output: data/prebrief_context.md

Policy:
- No live network calls outside of explicitly enabled sources (gmail, yahoo)
- Dry-run mode is always offline (fixtures only)
- Graceful degradation: missing sources log warnings but continue
- Config loading from .env and config.yaml
- Output metadata includes source info and timestamps

Usage:
    # Dry-run with all sources (fixtures)
    python scripts/run_prebrief.py --dry-run

    # Dry-run with calendar only
    python scripts/run_prebrief.py --dry-run --sources calendar

    # Live run with all available sources
    python scripts/run_prebrief.py --sources all

    # Live run with specific sources
    python scripts/run_prebrief.py --sources calendar,gmail

    # Live run with default sources (calendar, gmail)
    python scripts/run_prebrief.py
"""

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from second_brain.connectors.prebrief_builder import (
    PrebriefBuilder,
    PrebriefMarkdownRenderer,
)
from second_brain.connectors.schemas import CalendarEvent, InboxEmail
from second_brain.connectors.fixture_loader import (
    load_fixture_emails,
    load_fixture_events,
)


class PrebriefConfig:
    """Load and manage prebrief configuration."""

    def __init__(self, dry_run: bool = False):
        """
        Initialize prebrief config.

        Args:
            dry_run: If True, use synthetic fixtures only
        """
        self.dry_run = dry_run
        self.output_dir = Path("data")
        self.reference_date = date.today()

        # Load environment variables
        self._load_env()

    def _load_env(self) -> None:
        """Load environment variables from .env and .env.local."""
        env_files = [".env", ".env.local"]
        for env_file in env_files:
            if Path(env_file).exists():
                with open(env_file) as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" in line:
                            key, value = line.split("=", 1)
                            os.environ.setdefault(key.strip(), value.strip())

    @property
    def gmail_username(self) -> Optional[str]:
        """Get Gmail IMAP username from config."""
        return os.environ.get("GMAIL_IMAP_USERNAME")

    @property
    def gmail_password(self) -> Optional[str]:
        """Get Gmail IMAP app password from config."""
        return os.environ.get("GMAIL_IMAP_APP_PASSWORD")

    @property
    def yahoo_username(self) -> Optional[str]:
        """Get Yahoo IMAP username from config."""
        return os.environ.get("YAHOO_IMAP_USERNAME")

    @property
    def yahoo_password(self) -> Optional[str]:
        """Get Yahoo IMAP app password from config."""
        return os.environ.get("YAHOO_IMAP_APP_PASSWORD")

    def has_gmail_credentials(self) -> bool:
        """Check if Gmail credentials are configured."""
        return bool(self.gmail_username and self.gmail_password)

    def has_yahoo_credentials(self) -> bool:
        """Check if Yahoo credentials are configured."""
        return bool(self.yahoo_username and self.yahoo_password)


class PrebriefRunner:
    """Run prebrief generation with multiple sources."""

    def __init__(
        self,
        config: PrebriefConfig,
        sources: Optional[list[str]] = None,
    ):
        """
        Initialize runner.

        Args:
            config: PrebriefConfig instance
            sources: List of source names to include (calendar, gmail, yahoo)
                     or None for defaults (calendar, gmail)
        """
        self.config = config
        self.sources = sources or ["calendar", "gmail"]
        self.events: list[CalendarEvent] = []
        self.emails: list[InboxEmail] = []
        self.errors: dict[str, str] = {}

    def run(self) -> dict:
        """
        Run prebrief generation.

        Returns:
            Dictionary with keys:
            - success: bool
            - context: DailyContext dict if successful
            - events: list of normalized events
            - emails: list of normalized emails
            - sources: list of sources that succeeded
            - errors: dict of source -> error message
        """
        # Ensure output directory exists
        self._ensure_output_dir()

        # Load sources
        self._load_sources()

        # Build context
        if not self.events and not self.emails:
            print(
                "⚠️  No events or emails loaded. Cannot build prebrief.",
                file=sys.stderr,
            )
            return {
                "success": False,
                "context": None,
                "events": [],
                "emails": [],
                "sources": [],
                "errors": self.errors,
            }

        builder = PrebriefBuilder(reference_date=self.config.reference_date)
        context = builder.build(self.events, self.emails)

        # Write outputs
        json_file = self.config.output_dir / "prebrief_context.json"
        md_file = self.config.output_dir / "prebrief_context.md"

        self._write_json(context, json_file)
        self._write_markdown(context, md_file)

        # Prepare result
        sources_ok = [
            s for s in self.sources if s not in self.errors
        ]
        
        return {
            "success": True,
            "context": context.to_dict(),
            "events": [e.to_dict() for e in self.events],
            "emails": [e.to_dict() for e in self.emails],
            "sources": sources_ok,
            "errors": self.errors,
            "output_json": str(json_file),
            "output_md": str(md_file),
        }

    def _ensure_output_dir(self) -> None:
        """Create output directory if it doesn't exist."""
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

    def _load_sources(self) -> None:
        """Load events and emails from enabled sources."""
        for source in self.sources:
            if source == "calendar":
                self._load_calendar()
            elif source == "gmail":
                self._load_gmail()
            elif source == "yahoo":
                self._load_yahoo()
            else:
                print(f"⚠️  Unknown source: {source}", file=sys.stderr)

    def _load_calendar(self) -> None:
        """Load calendar events."""
        try:
            if self.config.dry_run:
                # Use synthetic fixtures
                raw_events = load_fixture_events()
                self.events.extend(raw_events)
                print(f"✓ Calendar: loaded {len(raw_events)} synthetic events (dry-run)")
            else:
                # TODO: Implement live calendar loading (Batch 8+)
                print(
                    "⚠️  Calendar: live loading not yet implemented (Batch 8+)",
                    file=sys.stderr,
                )
                self.errors["calendar"] = "Live loading not implemented"
        except Exception as e:
            msg = f"Calendar load failed: {e}"
            print(f"✗ {msg}", file=sys.stderr)
            self.errors["calendar"] = msg

    def _load_gmail(self) -> None:
        """Load Gmail emails."""
        try:
            if self.config.dry_run:
                # Use synthetic fixtures (already normalized)
                emails = load_fixture_emails()
                # Override source for consistency
                for email in emails:
                    email.source = "gmail"
                self.emails.extend(emails)
                print(f"✓ Gmail: loaded {len(emails)} synthetic emails (dry-run)")
            else:
                # Check credentials
                if not self.config.has_gmail_credentials():
                    msg = "Gmail credentials not configured"
                    print(f"⚠️  Gmail: {msg}", file=sys.stderr)
                    self.errors["gmail"] = msg
                    return

                # TODO: Implement live Gmail loading (Batch 8+)
                print(
                    "⚠️  Gmail: live loading not yet implemented (Batch 8+)",
                    file=sys.stderr,
                )
                self.errors["gmail"] = "Live loading not implemented"
        except Exception as e:
            msg = f"Gmail load failed: {e}"
            print(f"✗ {msg}", file=sys.stderr)
            self.errors["gmail"] = msg

    def _load_yahoo(self) -> None:
        """Load Yahoo emails."""
        try:
            if self.config.dry_run:
                # Use synthetic fixtures (already normalized, override source)
                emails = load_fixture_emails()
                # Override source to yahoo
                for email in emails:
                    email.source = "yahoo"
                self.emails.extend(emails)
                print(f"✓ Yahoo: loaded {len(emails)} synthetic emails (dry-run)")
            else:
                # Check credentials
                if not self.config.has_yahoo_credentials():
                    msg = "Yahoo credentials not configured"
                    print(f"⚠️  Yahoo: {msg}", file=sys.stderr)
                    self.errors["yahoo"] = msg
                    return

                # TODO: Implement live Yahoo loading (Batch 8+)
                print(
                    "⚠️  Yahoo: live loading not yet implemented (Batch 8+)",
                    file=sys.stderr,
                )
                self.errors["yahoo"] = "Live loading not implemented"
        except Exception as e:
            msg = f"Yahoo load failed: {e}"
            print(f"✗ {msg}", file=sys.stderr)
            self.errors["yahoo"] = msg

    def _write_json(self, context, output_path: Path) -> None:
        """Write DailyContext to JSON file."""
        try:
            with open(output_path, "w") as f:
                f.write(context.to_json())
            print(f"✓ Wrote: {output_path}")
        except Exception as e:
            msg = f"JSON write failed: {e}"
            print(f"✗ {msg}", file=sys.stderr)
            self.errors["json_write"] = msg

    def _write_markdown(self, context, output_path: Path) -> None:
        """Write DailyContext to Markdown file."""
        try:
            md = PrebriefMarkdownRenderer.render(context)
            with open(output_path, "w") as f:
                f.write(md)
            print(f"✓ Wrote: {output_path}")
        except Exception as e:
            msg = f"Markdown write failed: {e}"
            print(f"✗ {msg}", file=sys.stderr)
            self.errors["md_write"] = msg


def main():
    """Parse arguments and run prebrief."""
    parser = argparse.ArgumentParser(
        description="Generate daily prebrief from calendar + email sources"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use synthetic fixtures instead of live sources (offline)",
    )
    parser.add_argument(
        "--sources",
        type=str,
        default="calendar,gmail",
        help="Comma-separated list of sources (calendar, gmail, yahoo) or 'all'",
    )
    parser.add_argument(
        "--date",
        type=str,
        help="Reference date (YYYY-MM-DD, defaults to today)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data"),
        help="Output directory for prebrief_context.json and .md",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Write only JSON output (not Markdown)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress output messages",
    )

    args = parser.parse_args()

    # Parse sources
    if args.sources.lower() == "all":
        sources = ["calendar", "gmail", "yahoo"]
    else:
        sources = [s.strip() for s in args.sources.split(",")]

    # Setup config
    config = PrebriefConfig(dry_run=args.dry_run)
    if args.output_dir:
        config.output_dir = args.output_dir
    if args.date:
        try:
            config.reference_date = date.fromisoformat(args.date)
        except ValueError:
            print(f"✗ Invalid date format: {args.date}", file=sys.stderr)
            return 1

    # Run
    runner = PrebriefRunner(config, sources)
    result = runner.run()

    # Output result
    if not args.quiet:
        if result["success"]:
            print(f"\n✓ Prebrief built successfully!")
            print(f"  Events: {len(result['events'])}")
            print(f"  Emails: {len(result['emails'])}")
            print(f"  Sources: {', '.join(result['sources'])}")
            if result.get("output_json"):
                print(f"  JSON: {result['output_json']}")
            if result.get("output_md"):
                print(f"  Markdown: {result['output_md']}")
        else:
            print(f"\n✗ Prebrief generation failed")
            if result["errors"]:
                print(f"  Errors: {result['errors']}")

    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
