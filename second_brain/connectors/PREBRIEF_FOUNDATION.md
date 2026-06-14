# Prebrief Foundation

Status: Batch 7 - Runner + write-out layer (entry point) | Batch 6 - Prebrief builder (combining, ranking, rendering) | Batch 5 - Reserved for future | Batch 4 - Yahoo normalization | Batch 3 - Email normalization | Batch 2 - Calendar normalization

## Purpose
This module establishes the normalized schema and synthetic fixture baseline for PersGraph's calendar + email prebrief layer.

**Batch 7 adds**: The CLI runner and output layer — a production-ready entry point for generating daily prebriefs from configured calendar and email sources.

Batch 7 (Current) - Prebrief runner + write-out layer (entry point):
- `scripts/run_prebrief.py`: Command-line runner orchestrating the full prebrief generation pipeline
- `PrebriefConfig`: Loads environment config from `.env` and `.env.local`; manages output paths and reference dates
- `PrebriefRunner`: Main orchestration class that loads sources, combines data, builds context, and writes outputs
- Source loading with dry-run fixture support: calendar (4 synthetic events), gmail (7 synthetic emails), yahoo (7 synthetic emails)
- Partial failure handling: one source failing doesn't abort the whole run; errors tracked and reported
- Output writing: `data/prebrief_context.json` (machine-readable) and `data/prebrief_context.md` (human-readable)
- CLI with arguments: `--dry-run`, `--sources calendar,gmail,yahoo` (or 'all'), `--date YYYY-MM-DD`, `--output-dir PATH`, `--json-only`, `--quiet`
- No live network calls (dry-run always uses fixtures); live sources stub-ready for Batch 8
- Graceful degradation: missing credentials logged as warnings, not failures
- 39 comprehensive tests covering: config loading, dry-run workflows, source filtering, partial failures, output writing, edge cases
- Offline, deterministic, fixture-only (no live network calls outside of explicitly enabled sources)

Batch 6 - Prebrief builder (combining, ranking, rendering):
- `prebrief_builder.py`: Combines normalized CalendarEvent and InboxEmail inputs into DailyContext
- Generates machine-readable JSON (data/prebrief_context.json format) and human-readable Markdown
- Implements ranking/capping logic for: events_today, events_upcoming, bills_due, followups_needed, worth_checking, carry_forward
- Suggested priorities generation (urgent bills, followups, early events)
- Markdown rendering with emoji indicators and formatted sections
- Updated fixtures to match current schemas (CalendarEvent, InboxEmail, DailyContext)
- 37 comprehensive tests covering ranking, building, rendering, and integration workflows
- Offline, deterministic, fixture-only (no live network calls, no real user data)
- Aligns with existing schemas in `second_brain/connectors/schemas.py`

Batch 1 includes:
- normalized dataclasses in `second_brain/connectors/schemas.py`
- synthetic JSON fixtures under `tests/fixtures/prebrief/`
- schema and fixture tests under `tests/test_prebrief/`

Batch 2 extends Batch 1 with:
- `calendar_normalizer.py`: Calendar event normalization with dry-run fixture support
- Category inference for events: `work`, `health`, `travel`, `personal`, `meeting`, `admin`
- Prep-needed detection based on category and title keywords
- `CalendarEventFilter` for date-range, single-date, category, and prep filtering
- `CalendarNormalizerBatch` for batch processing and helper methods (`events_today`, `events_upcoming`, `events_with_prep`)
- Sorting by start time (ascending/descending)
- Dry-run mode: fixtures only, no live OAuth or network calls
- 35+ comprehensive tests covering normalization, filtering, and batch operations

Batch 3 extends Batch 2 with:
- `email_normalizer.py`: Email normalization, classification, amount/date extraction
- Classification logic for buckets: `bill`, `followup`, `worth_checking`, `fyi`, `unclassified`
- Due-date extraction (handles "June 18", "6/18", "6-18-2026", day names)
- Amount extraction for bills (handles $123.45, comma-separated, variants)
- Urgency scoring (0-5 scale based on bucket + due date)
- Confidence scoring for classification reliability
- Batch processing for normalized email lists
- 52 comprehensive tests covering all extraction and classification logic

Batch 4 extends Batch 3 with:
- `yahoo_normalizer.py`: Yahoo-specific email normalization adapter
- Reuses Batch 3 EmailNormalizer for classification/extraction logic (no duplication)
- Yahoo metadata handling: UIDs, folders, flags (\Seen, \Flagged, \Deleted, etc.)
- YahooRawRecord dataclass for Yahoo-style email records with IMAP-like metadata
- YahooNormalizerBatch with filtering (by folder, flag, unread, flagged, etc.)
- Sorting and batch operations for Yahoo records
- Source attribution: normalized.source = "yahoo" + metadata in source_ref
- 61 comprehensive tests covering classification, metadata preservation, filtering, and error handling

## Fixture-only policy
- Never commit real email content, real inbox addresses, or exported calendar data.
- Test fixtures must use synthetic domains like `.example` and `.test`.
- No credentials, tokens, or app passwords belong in repo fixtures, tests, or docs.

## Schema contract
The Batch 1 schema contract intentionally matches the reviewed prebrief plan and is designed for later phases:
- `CalendarEvent`
- `InboxEmail`
- `PreBriefSection`
- `DailyContext`

These are the foundation for:
- calendar normalization
- Gmail/Yahoo normalization
- bill/follow-up/worth-checking classification
- prebrief JSON generation for Morning Brief handoff

## Developer guidance
- Keep tests offline and deterministic.
- Prefer JSON fixture files over embedded real-world samples.
- Treat `DailyContext` JSON as the future machine-readable handoff contract.
- Use `EmailNormalizer` to convert raw email-like records (from API, fixture, etc.)
- Classification is heuristic-only in Batch 3; LLM refinement in future batches
- All extraction patterns handle case-insensitive matching
- Batch operations preserve order and handle both RawEmailRecord and dict formats

## Batch 2 Implementation Details

### CalendarNormalizer class
Core normalization logic with:
- `normalize(raw_record)` → CalendarEvent
- `_parse_datetime()` - ISO string or datetime object parsing
- `_infer_category()` - Keyword-based category inference
- `_infer_prep_needed()` - Detect if event needs preparation

### CalendarEventFilter class (static methods)
Date-range and attribute filtering:
- `by_date_range(events, start_date, end_date)` - Events overlapping date range
- `by_date(events, target_date)` - Events on specific date
- `by_category(events, category)` - Filter by category
- `prep_needed(events)` - Filter events requiring prep
- `sort_by_start_time(events, reverse)` - Sort by start_time

### CalendarNormalizerBatch class
Batch operations:
- `normalize_batch(raw_records)` → list[CalendarEvent]
- `events_today(events, reference_date)` - Events for specific date, sorted
- `events_upcoming(events, days_ahead, reference_date)` - Next N days (excluding today)
- `events_with_prep(events)` - Events needing prep, sorted

### Category inference
1. Use provided category if valid
2. Keyword matching: `work`, `health`, `travel`, `personal`
3. Default to `admin`

### Prep-needed inference
- Work category → always needs prep
- Health appointments → needs prep ("appointment", "checkup", "vaccination", "lab")
- Travel → needs prep ("flight", "trip", "travel")
- Personal/other → no prep by default

## Batch 3 Implementation Details

### EmailNormalizer class
Core normalization logic with:
- `normalize(raw_record, reference_date)` → InboxEmail
- `_classify_bucket()` - Heuristic-based classification (keyword scoring)
- `_extract_amount()` - Amount parsing ($123.45 patterns)
- `_extract_due_date()` - Relative date extraction
- `_calculate_urgency()` - 0-5 scale based on bucket + due date
- `_calculate_confidence()` - 0.0-1.0 reliability score

### EmailNormalizerBatch class
For processing multiple emails:
- `normalize_batch(raw_records, reference_date)` → list[InboxEmail]
- Supports both RawEmailRecord and dict inputs

### Date parsing strategies
1. Numeric patterns: `6/18`, `6-18-2026`, `6/18/2026`
2. Month names: `June 18`, `June 18 2026`
3. Day names: `Friday` → next occurrence
4. Relative dates: Past month → next year

### Urgency scale
- 0: FYI (no action needed)
- 1: Worth checking (informational)
- 2: Followup or bill >14 days away
- 3: Bill 3-7 days away
- 4: Bill 1-2 days away
- 5: Overdue (< today)

## Batch 4 Implementation Details

### YahooRawRecord dataclass
Synthetic Yahoo-style email record with:
- `uid`: Unique identifier (Yahoo internal or synthetic)
- `sender`, `subject`, `snippet`, `timestamp`: Standard email fields
- `folder`: INBOX, [YAHOO]/ARCHIVE, SPAM, TRASH, etc.
- `flags`: IMAP-like flags (\Seen, \Flagged, \Deleted)
- `internaldate`: Optional Yahoo internal date metadata
- `yahoo_message_id`: Optional Yahoo unique message ID
- `labels`, `thread_key`, `source_ref`: Standard metadata

### YahooNormalizer class
Adapter that reuses Batch 3 EmailNormalizer:
- `normalize(yahoo_record, reference_date)` → InboxEmail
  - Converts YahooRawRecord to RawEmailRecord
  - Uses EmailNormalizer for classification/extraction
  - Overrides source to "yahoo"
  - Preserves Yahoo metadata in source_ref
- Flag detection helpers:
  - `_is_read(flags)` - Checks for \Seen flag
  - `_is_flagged(flags)` - Checks for \Flagged flag
  - `_is_deleted(flags)` - Checks for \Deleted flag
  - `_is_in_trash(folder)` - Checks if email is in trash-like folder
  - `_is_spam(folder)` - Checks if email is in spam folder

### YahooNormalizerBatch class
Batch operations for Yahoo records:
- `normalize_batch(yahoo_records, reference_date)` → list[InboxEmail]
  - Supports both YahooRawRecord and dict inputs
- Filtering methods (all return filtered list):
  - `filter_by_folder(records, folder)` - Filter by folder name
  - `filter_by_flag(records, flag)` - Filter by flag (case-insensitive)
  - `filter_unread(records)` - Only emails without \Seen flag
  - `filter_flagged(records)` - Only emails with \Flagged flag
  - `filter_not_deleted(records)` - Exclude deleted emails and trash
  - `filter_not_spam(records)` - Exclude spam/junk folders
- Sorting methods:
  - `sort_by_timestamp(records, reverse=False)` - Sort by received time

### Source attribution pattern
Yahoo records are marked with:
- `normalized.source = "yahoo"`
- `normalized.source_ref = "yahoo:folder=INBOX|flags=..."` (compact metadata)
- Preserves all metadata: folder, flags, internaldate, yahoo_message_id

### Design principles for Batch 4
- **No duplication**: Reuses EmailNormalizer from Batch 3 rather than re-implementing classification/extraction
- **Adapter pattern**: YahooNormalizer bridges Yahoo-specific metadata → normalized InboxEmail
- **Lightweight**: Only adds Yahoo-specific logic (metadata handling, folder/flag filtering)
- **Synthetic only**: All tests use synthetic domains (.example, .test), no real data
- **Offline**: No live IMAP access, no credentials, deterministic fixture-based testing

## Current test scope

Batch 1 & common:
- construct objects from fixture dicts
- serialize/deserialize schema objects
- validate synthetic fixture loading
- round-trip `DailyContext` JSON

Batch 2 (Calendar normalization):
- **NEW**: Basic normalization (3 tests)
- **NEW**: Category inference (7 tests)
- **NEW**: Prep-needed inference (6 tests)
- **NEW**: Date-range filtering (4 tests)
- **NEW**: Single date filtering (1 test)
- **NEW**: Category filtering (1 test)
- **NEW**: Prep-needed filtering (1 test)
- **NEW**: Sort by start time (2 tests)
- **NEW**: Batch normalization (3 tests)
- **NEW**: Batch helper methods (3 tests)
- **NEW**: Schema preservation (9 tests)
- **NEW**: Edge cases (9 tests)
- **NEW**: Integration tests (2 tests)

**Batch 2 total: 51 tests, all passing**

Batch 3 (Email normalization):
- Bucket classification (7 tests)
- Amount extraction (5 tests)
- Date extraction (6 tests)
- Urgency calculation (7 tests)
- Confidence scoring (3 tests)
- Action flags (4 tests)
- Schema preservation (9 tests)
- Batch processing (3 tests)
- Integration tests (2 tests)
- Edge cases (6 tests)

**Batch 3 total: 52 tests, all passing**

Batch 4 (Yahoo normalization):
- Yahoo record normalization (5 tests)
- Amount extraction from Yahoo records (3 tests)
- Due-date extraction from Yahoo records (3 tests)
- Yahoo metadata preservation in normalized output (8 tests)
- IMAP flag detection helpers (11 tests)
- Batch normalization (3 tests)
- Batch filtering by folder, flag, read status (10 tests)
- Batch sorting by timestamp (3 tests)
- Schema normalization (3 tests)
- Config and error handling (9 tests)
- Integration tests (4 tests)

**Batch 4 total: 61 tests, all passing**

Batch 6 (Prebrief builder - combining, ranking, rendering):
- `prebrief_builder.py`: Core module combining normalized CalendarEvent and InboxEmail into DailyContext
- `PrebriefContextRanker`: Ranking/capping logic for each section
  - `rank_and_cap_events_today()` - By start_time (ascending)
  - `rank_and_cap_events_upcoming()` - By start_time (ascending)
  - `rank_and_cap_bills_due()` - By due_date (ascending), then urgency (descending)
  - `rank_and_cap_followups_needed()` - By urgency (descending), then timestamp (ascending)
  - `rank_and_cap_worth_checking()` - By urgency, confidence, timestamp
  - `rank_and_cap_carry_forward()` - By timestamp (oldest first)
- `PrebriefBuilder`: Main builder class
  - `build(events, emails)` → DailyContext
  - Section cap configuration (defaults in DEFAULT_SECTION_CAPS)
  - Reference date handling (defaults to today)
  - Suggested priorities generation (urgent bills, followups, early events)
- `PrebriefMarkdownRenderer`: Human-readable Markdown output
  - `render(context)` → Markdown string
  - Sections: title, priorities, events_today, events_upcoming, bills_due, followups_needed, worth_checking, carry_forward
  - Emoji indicators for urgency and section types
  - Capping indicators when sections are truncated
- Updated fixtures:
  - `tests/fixtures/prebrief/calendar_events.py` - Aligned to CalendarEvent schema
  - `tests/fixtures/prebrief/inbox_emails.py` - Aligned to InboxEmail schema with bucket classification
  - `tests/fixtures/prebrief/daily_context.py` - Sample and empty contexts for testing
- 37 comprehensive tests covering:
  - Ranking and capping logic (13 tests)
  - Builder core functionality (5 tests)
  - Priority generation (5 tests)
  - Serialization (2 tests)
  - Markdown rendering (7 tests)
  - Integration workflows (3 tests)

**Batch 6 total: 37 tests, all passing**

## Batch 7 Implementation Details

### PrebriefConfig class
Configuration management with:
- `__init__(dry_run=False)` - Initialize with dry-run mode flag
- `_load_env()` - Load `.env` and `.env.local` files
- Properties: `gmail_username`, `gmail_password`, `yahoo_username`, `yahoo_password`
- Methods: `has_gmail_credentials()`, `has_yahoo_credentials()`
- Attributes: `dry_run`, `output_dir`, `reference_date`

### PrebriefRunner class
Orchestrates prebrief generation with:
- `__init__(config, sources=None)` - Initialize with config and source list
- `run()` → dict - Execute full pipeline: load → build → write → report
- `_ensure_output_dir()` - Create output directory if missing
- `_load_sources()` - Iterate over sources and call appropriate loaders
- `_load_calendar()` - Load calendar events (synthetic or live stub)
- `_load_gmail()` - Load Gmail emails (synthetic or live stub)
- `_load_yahoo()` - Load Yahoo emails (synthetic or live stub)
- `_write_json(context, path)` - Write DailyContext to JSON
- `_write_markdown(context, path)` - Write DailyContext to Markdown

### CLI entrypoint (main function)
Command-line interface with arguments:
- `--dry-run` - Use synthetic fixtures only
- `--sources` - Comma-separated source names (default: "calendar,gmail")
- `--date` - Reference date (YYYY-MM-DD, default: today)
- `--output-dir` - Output directory (default: data)
- `--json-only` - Write JSON only, skip Markdown
- `--quiet` - Suppress output messages

### Usage examples
```bash
# Dry-run with all sources
python scripts/run_prebrief.py --dry-run

# Dry-run calendar only
python scripts/run_prebrief.py --dry-run --sources calendar

# Live run with specific sources
python scripts/run_prebrief.py --sources calendar,gmail

# Live run all sources
python scripts/run_prebrief.py --sources all
```

### Design principles
- **Offline-first**: Dry-run always uses fixtures; live sources are gracefully stubs
- **Partial failure**: One source failing doesn't abort the whole run
- **Graceful degradation**: Missing credentials logged as warnings, not failures
- **Fixture-only testing**: All tests use synthetic data, no live network calls
- **Clear output**: JSON machine-readable, Markdown human-readable
- **Source attribution**: Each item tagged with source (calendar, gmail, yahoo)

Batch 7 (Runner + write-out):
- Config initialization (9 tests)
- Dry-run workflows with single/multiple sources (5 tests)
- Output directory creation and file writing (4 tests)
- Partial failure handling (4 tests)
- Source filtering (5 tests)
- Integration workflows (8 tests)
- Config loading and environment handling (2 tests)
- Edge cases (2 tests)

**Batch 7 total: 39 tests, all passing**

**Overall: 253 tests (9 existing + 51 Batch 2 + 52 Batch 3 + 61 Batch 4 + 37 Batch 6 + 39 Batch 7), all passing**
