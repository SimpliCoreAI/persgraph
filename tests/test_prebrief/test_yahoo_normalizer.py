"""
Tests for Yahoo email normalization (Batch 4).

Uses only synthetic fixtures. No real Yahoo data, no live IMAP, no credentials.
Tests reuse of Batch 3 EmailNormalizer logic plus Yahoo-specific metadata handling.
"""

import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from second_brain.connectors.yahoo_normalizer import (
    YahooNormalizer,
    YahooNormalizerBatch,
    YahooRawRecord,
)
from second_brain.connectors.schemas import InboxEmail
from second_brain.connectors.email_normalizer import (
    BUCKET_BILL,
    BUCKET_FOLLOWUP,
    BUCKET_FYI,
    BUCKET_WORTH_CHECKING,
    BUCKET_UNCLASSIFIED,
)


# ── Test fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def normalizer():
    return YahooNormalizer()


@pytest.fixture
def batch_normalizer():
    return YahooNormalizerBatch()


@pytest.fixture
def reference_date():
    return date(2026, 6, 15)


def sample_yahoo_bill() -> YahooRawRecord:
    """Sample bill email from Yahoo."""
    return YahooRawRecord(
        uid="yahoo_001",
        sender="billing@fakebank.test",
        subject="Your statement is ready — due June 18",
        snippet="Payment due June 18. Amount: $142.50.",
        timestamp="2026-06-14T08:00:00+00:00",
        folder="INBOX",
        flags=["\\Seen"],
        labels=["billing"],
        thread_key="t_yahoo_fakebank",
    )


def sample_yahoo_followup() -> YahooRawRecord:
    """Sample followup email from Yahoo."""
    return YahooRawRecord(
        uid="yahoo_002",
        sender="school@example.test",
        subject="Re: permission slip for field trip",
        snippet="Please sign and return by Friday.",
        timestamp="2026-06-13T16:30:00+00:00",
        folder="INBOX",
        flags=["\\Seen", "\\Flagged"],
        labels=["school"],
        thread_key="t_yahoo_fieldtrip",
    )


def sample_yahoo_worth_checking() -> YahooRawRecord:
    """Sample worth-checking email from Yahoo."""
    return YahooRawRecord(
        uid="yahoo_003",
        sender="alerts@travelco.example",
        subject="Flight time change for your July trip",
        snippet="Your July 4 departure has moved from 9:00am to 11:30am.",
        timestamp="2026-06-14T10:00:00+00:00",
        folder="INBOX",
        flags=[],
        thread_key="t_yahoo_travel",
    )


def sample_yahoo_fyi() -> YahooRawRecord:
    """Sample FYI email from Yahoo."""
    return YahooRawRecord(
        uid="yahoo_004",
        sender="newsletter@promos.example",
        subject="This week's deals!",
        snippet="Check out our latest offers...",
        timestamp="2026-06-14T07:00:00+00:00",
        folder="INBOX",
        flags=[],
        thread_key="t_yahoo_promo",
    )


def sample_yahoo_unclassified() -> YahooRawRecord:
    """Sample unclassified email from Yahoo."""
    return YahooRawRecord(
        uid="yahoo_005",
        sender="friend@example.test",
        subject="Hey",
        snippet="Just wanted to catch up.",
        timestamp="2026-06-14T12:00:00+00:00",
        folder="INBOX",
        flags=["\\Seen"],
    )


def sample_yahoo_archived() -> YahooRawRecord:
    """Sample archived email from Yahoo."""
    return YahooRawRecord(
        uid="yahoo_archive_001",
        sender="vendor@example.test",
        subject="Previous invoice",
        snippet="Archived for reference.",
        timestamp="2026-05-01T10:00:00+00:00",
        folder="[YAHOO]/ARCHIVE",
        flags=["\\Seen"],
    )


def sample_yahoo_spam() -> YahooRawRecord:
    """Sample spam email from Yahoo."""
    return YahooRawRecord(
        uid="yahoo_spam_001",
        sender="spam@malicious.example",
        subject="YOU WON THE LOTTERY!!!",
        snippet="Claim your prize now.",
        timestamp="2026-06-14T06:00:00+00:00",
        folder="SPAM",
        flags=[],
    )


def sample_yahoo_trash() -> YahooRawRecord:
    """Sample deleted email from Yahoo."""
    return YahooRawRecord(
        uid="yahoo_trash_001",
        sender="vendor@example.test",
        subject="Old email",
        snippet="Marked for deletion.",
        timestamp="2026-06-10T10:00:00+00:00",
        folder="TRASH",
        flags=["\\Deleted"],
    )


# ── Classification tests (reuse Batch 3 logic) ────────────────────────────────


class TestYahooBucketClassification:
    """Test that Yahoo records classify correctly via Batch 3 normalizer."""

    def test_classify_yahoo_bill(self, normalizer, reference_date):
        raw = sample_yahoo_bill()
        result = normalizer.normalize(raw, reference_date)
        assert result.bucket == BUCKET_BILL

    def test_classify_yahoo_followup(self, normalizer, reference_date):
        raw = sample_yahoo_followup()
        result = normalizer.normalize(raw, reference_date)
        assert result.bucket == BUCKET_FOLLOWUP

    def test_classify_yahoo_worth_checking(self, normalizer, reference_date):
        raw = sample_yahoo_worth_checking()
        result = normalizer.normalize(raw, reference_date)
        assert result.bucket == BUCKET_WORTH_CHECKING

    def test_classify_yahoo_fyi(self, normalizer, reference_date):
        raw = sample_yahoo_fyi()
        result = normalizer.normalize(raw, reference_date)
        assert result.bucket == BUCKET_FYI

    def test_classify_yahoo_unclassified(self, normalizer, reference_date):
        raw = sample_yahoo_unclassified()
        result = normalizer.normalize(raw, reference_date)
        assert result.bucket == BUCKET_UNCLASSIFIED


# ── Amount and date extraction tests (reuse Batch 3 logic) ───────────────────


class TestYahooAmountExtraction:
    """Test amount extraction for Yahoo records."""

    def test_extract_amount_from_yahoo_bill(self, normalizer):
        raw = sample_yahoo_bill()
        result = normalizer.normalize(raw)
        assert result.amount == 142.50

    def test_extract_amount_with_comma(self, normalizer):
        raw = YahooRawRecord(
            uid="test_amount",
            sender="vendor@example.test",
            subject="Invoice",
            snippet="Amount: $1,234.56",
            timestamp="2026-06-14T08:00:00+00:00",
        )
        result = normalizer.normalize(raw)
        assert result.amount == 1234.56

    def test_no_amount_for_fyi(self, normalizer):
        raw = sample_yahoo_fyi()
        result = normalizer.normalize(raw)
        assert result.amount is None


class TestYahooDueDateExtraction:
    """Test due date extraction for Yahoo records."""

    def test_extract_due_date_from_yahoo_bill(self, normalizer, reference_date):
        raw = sample_yahoo_bill()
        result = normalizer.normalize(raw, reference_date)
        assert result.due_date == date(2026, 6, 18)

    def test_extract_due_date_day_name(self, normalizer, reference_date):
        raw = sample_yahoo_followup()
        result = normalizer.normalize(raw, reference_date)
        # "by Friday" from Monday June 15, 2026 = June 19
        assert result.due_date == date(2026, 6, 19)

    def test_no_due_date_for_fyi(self, normalizer, reference_date):
        raw = sample_yahoo_fyi()
        result = normalizer.normalize(raw, reference_date)
        assert result.due_date is None


# ── Yahoo metadata preservation tests ─────────────────────────────────────────


class TestYahooMetadataPreservation:
    """Test that Yahoo-specific metadata is properly preserved."""

    def test_normalized_source_is_yahoo(self, normalizer):
        raw = sample_yahoo_bill()
        result = normalizer.normalize(raw)
        assert result.source == "yahoo"

    def test_uid_becomes_id(self, normalizer):
        raw = sample_yahoo_bill()
        result = normalizer.normalize(raw)
        assert result.id == "yahoo_001"

    def test_folder_preserved_in_source_ref(self, normalizer):
        raw = sample_yahoo_bill()
        result = normalizer.normalize(raw)
        assert "folder=INBOX" in result.source_ref

    def test_flags_preserved_in_source_ref(self, normalizer):
        raw = YahooRawRecord(
            uid="test_flags",
            sender="vendor@example.test",
            subject="Test",
            snippet="Test",
            timestamp="2026-06-14T08:00:00+00:00",
            flags=["\\Seen", "\\Flagged"],
        )
        result = normalizer.normalize(raw)
        assert "flags=" in result.source_ref

    def test_labels_preserved(self, normalizer):
        raw = sample_yahoo_bill()
        result = normalizer.normalize(raw)
        assert "billing" in result.labels

    def test_thread_key_preserved(self, normalizer):
        raw = sample_yahoo_bill()
        result = normalizer.normalize(raw)
        assert result.thread_key == "t_yahoo_fakebank"

    def test_internaldate_in_source_ref(self, normalizer):
        raw = YahooRawRecord(
            uid="test_idate",
            sender="vendor@example.test",
            subject="Test",
            snippet="Test",
            timestamp="2026-06-14T08:00:00+00:00",
            internaldate="14-Jun-2026 08:00:00 +0000",
        )
        result = normalizer.normalize(raw)
        assert "internaldate=" in result.source_ref

    def test_yahoo_message_id_in_source_ref(self, normalizer):
        raw = YahooRawRecord(
            uid="test_msgid",
            sender="vendor@example.test",
            subject="Test",
            snippet="Test",
            timestamp="2026-06-14T08:00:00+00:00",
            yahoo_message_id="yahoo123456",
        )
        result = normalizer.normalize(raw)
        assert "yahoo_message_id=yahoo123456" in result.source_ref


# ── Yahoo flag helper tests ───────────────────────────────────────────────────


class TestYahooFlagHelpers:
    """Test Yahoo flag detection methods."""

    def test_is_read(self, normalizer):
        raw = YahooRawRecord(
            uid="test_read",
            sender="vendor@example.test",
            subject="Test",
            snippet="Test",
            timestamp="2026-06-14T08:00:00+00:00",
            flags=["\\Seen"],
        )
        assert normalizer._is_read(raw.flags) is True

    def test_is_not_read(self, normalizer):
        raw = YahooRawRecord(
            uid="test_unread",
            sender="vendor@example.test",
            subject="Test",
            snippet="Test",
            timestamp="2026-06-14T08:00:00+00:00",
            flags=[],
        )
        assert normalizer._is_read(raw.flags) is False

    def test_is_flagged(self, normalizer):
        raw = sample_yahoo_followup()  # Has "\\Flagged"
        assert normalizer._is_flagged(raw.flags) is True

    def test_is_not_flagged(self, normalizer):
        raw = sample_yahoo_bill()  # Only "\\Seen"
        assert normalizer._is_flagged(raw.flags) is False

    def test_is_deleted(self, normalizer):
        raw = sample_yahoo_trash()
        assert normalizer._is_deleted(raw.flags) is True

    def test_is_not_deleted(self, normalizer):
        raw = sample_yahoo_bill()
        assert normalizer._is_deleted(raw.flags) is False

    def test_is_in_trash(self, normalizer):
        raw = sample_yahoo_trash()
        assert normalizer._is_in_trash(raw.folder) is True

    def test_is_in_inbox(self, normalizer):
        raw = sample_yahoo_bill()
        assert normalizer._is_in_trash(raw.folder) is False

    def test_is_spam(self, normalizer):
        raw = sample_yahoo_spam()
        assert normalizer._is_spam(raw.folder) is True

    def test_is_not_spam(self, normalizer):
        raw = sample_yahoo_bill()
        assert normalizer._is_spam(raw.folder) is False

    def test_flag_case_insensitivity(self, normalizer):
        raw = YahooRawRecord(
            uid="test_case",
            sender="vendor@example.test",
            subject="Test",
            snippet="Test",
            timestamp="2026-06-14T08:00:00+00:00",
            flags=["\\seen", "\\flagged"],  # lowercase
        )
        assert normalizer._is_read(raw.flags) is True
        assert normalizer._is_flagged(raw.flags) is True


# ── Batch processing tests ────────────────────────────────────────────────────


class TestYahooBatchNormalization:
    """Test batch processing of Yahoo records."""

    def test_batch_normalize_list_of_records(self, batch_normalizer, reference_date):
        raw_list = [
            sample_yahoo_bill(),
            sample_yahoo_followup(),
            sample_yahoo_fyi(),
        ]
        results = batch_normalizer.normalize_batch(raw_list, reference_date)

        assert len(results) == 3
        assert results[0].bucket == BUCKET_BILL
        assert results[1].bucket == BUCKET_FOLLOWUP
        assert results[2].bucket == BUCKET_FYI

    def test_batch_normalize_list_of_dicts(self, batch_normalizer, reference_date):
        dicts = [
            {
                "uid": "yahoo_dict_001",
                "sender": "vendor@example.test",
                "subject": "Invoice due June 18",
                "snippet": "Amount: $100",
                "timestamp": "2026-06-14T08:00:00+00:00",
                "folder": "INBOX",
                "flags": ["\\Seen"],
                "labels": [],
            }
        ]
        results = batch_normalizer.normalize_batch(dicts, reference_date)

        assert len(results) == 1
        assert results[0].bucket == BUCKET_BILL
        assert results[0].amount == 100.0
        assert results[0].source == "yahoo"

    def test_batch_preserves_order(self, batch_normalizer, reference_date):
        raw_list = [
            sample_yahoo_bill(),
            sample_yahoo_followup(),
            sample_yahoo_worth_checking(),
            sample_yahoo_fyi(),
            sample_yahoo_unclassified(),
        ]
        results = batch_normalizer.normalize_batch(raw_list, reference_date)

        assert len(results) == 5
        assert results[0].id == "yahoo_001"
        assert results[1].id == "yahoo_002"
        assert results[2].id == "yahoo_003"
        assert results[3].id == "yahoo_004"
        assert results[4].id == "yahoo_005"


# ── Batch filtering tests ─────────────────────────────────────────────────────


class TestYahooBatchFiltering:
    """Test Yahoo-specific batch filtering methods."""

    def test_filter_by_folder(self, batch_normalizer):
        records = [
            sample_yahoo_bill(),
            sample_yahoo_archived(),
            sample_yahoo_spam(),
        ]
        inbox = batch_normalizer.filter_by_folder(records, "INBOX")
        assert len(inbox) == 1
        assert inbox[0].uid == "yahoo_001"

    def test_filter_by_folder_archived(self, batch_normalizer):
        records = [
            sample_yahoo_bill(),
            sample_yahoo_archived(),
        ]
        archived = batch_normalizer.filter_by_folder(records, "[YAHOO]/ARCHIVE")
        assert len(archived) == 1
        assert archived[0].uid == "yahoo_archive_001"

    def test_filter_by_flag_seen(self, batch_normalizer):
        records = [
            sample_yahoo_bill(),  # Has \Seen
            sample_yahoo_followup(),  # Has \Seen and \Flagged
            sample_yahoo_fyi(),  # No flags
        ]
        seen = batch_normalizer.filter_by_flag(records, "\\Seen")
        assert len(seen) == 2

    def test_filter_by_flag_flagged(self, batch_normalizer):
        records = [
            sample_yahoo_bill(),
            sample_yahoo_followup(),  # Has \Flagged
            sample_yahoo_fyi(),
        ]
        flagged = batch_normalizer.filter_by_flag(records, "\\Flagged")
        assert len(flagged) == 1
        assert flagged[0].uid == "yahoo_002"

    def test_filter_by_flag_case_insensitive(self, batch_normalizer):
        records = [
            sample_yahoo_bill(),
            sample_yahoo_followup(),
        ]
        flagged = batch_normalizer.filter_by_flag(records, "\\flagged")  # lowercase
        assert len(flagged) == 1

    def test_filter_unread(self, batch_normalizer):
        records = [
            sample_yahoo_bill(),  # \Seen
            sample_yahoo_followup(),  # \Seen
            sample_yahoo_worth_checking(),  # No flags (unread)
            sample_yahoo_fyi(),  # No flags (unread)
        ]
        unread = batch_normalizer.filter_unread(records)
        assert len(unread) == 2
        assert unread[0].uid == "yahoo_003"
        assert unread[1].uid == "yahoo_004"

    def test_filter_flagged(self, batch_normalizer):
        records = [
            sample_yahoo_bill(),
            sample_yahoo_followup(),  # Has \Flagged
            sample_yahoo_fyi(),
        ]
        flagged = batch_normalizer.filter_flagged(records)
        assert len(flagged) == 1
        assert flagged[0].uid == "yahoo_002"

    def test_filter_not_deleted(self, batch_normalizer):
        records = [
            sample_yahoo_bill(),
            sample_yahoo_trash(),  # Deleted + in TRASH
            sample_yahoo_spam(),
        ]
        not_deleted = batch_normalizer.filter_not_deleted(records)
        assert len(not_deleted) == 2
        assert all(r.uid != "yahoo_trash_001" for r in not_deleted)

    def test_filter_not_spam(self, batch_normalizer):
        records = [
            sample_yahoo_bill(),
            sample_yahoo_spam(),
            sample_yahoo_fyi(),
        ]
        not_spam = batch_normalizer.filter_not_spam(records)
        assert len(not_spam) == 2
        assert all(r.uid != "yahoo_spam_001" for r in not_spam)

    def test_chained_filters(self, batch_normalizer):
        """Test chaining multiple filters."""
        records = [
            sample_yahoo_bill(),
            sample_yahoo_followup(),
            sample_yahoo_spam(),
            sample_yahoo_trash(),
        ]
        # Only inbox (not spam, not deleted) and unread
        cleaned = batch_normalizer.filter_not_spam(records)
        cleaned = batch_normalizer.filter_not_deleted(cleaned)
        unread = batch_normalizer.filter_unread(cleaned)
        
        # Bill and followup are both read, so unread should be empty
        assert len(unread) == 0


# ── Batch sorting tests ───────────────────────────────────────────────────────


class TestYahooBatchSorting:
    """Test Yahoo-specific batch sorting."""

    def test_sort_by_timestamp_ascending(self, batch_normalizer):
        records = [
            sample_yahoo_bill(),  # 2026-06-14 08:00:00
            sample_yahoo_followup(),  # 2026-06-13 16:30:00 (earlier)
            sample_yahoo_worth_checking(),  # 2026-06-14 10:00:00 (later)
        ]
        sorted_records = batch_normalizer.sort_by_timestamp(records, reverse=False)

        assert sorted_records[0].uid == "yahoo_002"  # earliest
        assert sorted_records[1].uid == "yahoo_001"
        assert sorted_records[2].uid == "yahoo_003"  # latest

    def test_sort_by_timestamp_descending(self, batch_normalizer):
        records = [
            sample_yahoo_bill(),
            sample_yahoo_followup(),
            sample_yahoo_worth_checking(),
        ]
        sorted_records = batch_normalizer.sort_by_timestamp(records, reverse=True)

        assert sorted_records[0].uid == "yahoo_003"  # latest
        assert sorted_records[1].uid == "yahoo_001"
        assert sorted_records[2].uid == "yahoo_002"  # earliest

    def test_sort_handles_datetime_objects(self, batch_normalizer):
        """Verify sort handles datetime objects, not just strings."""
        records = [
            YahooRawRecord(
                uid="dt_001",
                sender="vendor@example.test",
                subject="Test 1",
                snippet="Test",
                timestamp=datetime(2026, 6, 14, 10, 0, 0),
            ),
            YahooRawRecord(
                uid="dt_002",
                sender="vendor@example.test",
                subject="Test 2",
                snippet="Test",
                timestamp=datetime(2026, 6, 14, 8, 0, 0),
            ),
        ]
        sorted_records = batch_normalizer.sort_by_timestamp(records, reverse=False)
        assert sorted_records[0].uid == "dt_002"
        assert sorted_records[1].uid == "dt_001"


# ── Schema normalization tests ────────────────────────────────────────────────


class TestYahooSchemaNormalization:
    """Test that normalized output matches InboxEmail schema."""

    def test_normalized_is_inbox_email(self, normalizer):
        raw = sample_yahoo_bill()
        result = normalizer.normalize(raw)
        assert isinstance(result, InboxEmail)

    def test_normalized_roundtrip_to_dict(self, normalizer):
        """Verify roundtrip to dict and back works."""
        raw = sample_yahoo_bill()
        original = normalizer.normalize(raw)
        restored = InboxEmail.from_dict(original.to_dict())
        assert restored == original

    def test_normalized_dict_has_required_fields(self, normalizer):
        raw = sample_yahoo_bill()
        normalized = normalizer.normalize(raw)
        d = normalized.to_dict()
        
        required_fields = {
            "id", "source", "sender", "subject", "timestamp",
            "snippet", "bucket", "urgency", "confidence"
        }
        assert required_fields.issubset(set(d.keys()))


# ── Config and error handling tests ───────────────────────────────────────────


class TestYahooConfigAndErrors:
    """Test error handling and edge cases with Yahoo records."""

    def test_empty_flags_list(self, normalizer):
        raw = YahooRawRecord(
            uid="test_empty_flags",
            sender="vendor@example.test",
            subject="Test",
            snippet="Test",
            timestamp="2026-06-14T08:00:00+00:00",
            flags=[],
        )
        result = normalizer.normalize(raw)
        assert isinstance(result, InboxEmail)

    def test_none_labels(self, normalizer):
        raw = YahooRawRecord(
            uid="test_none_labels",
            sender="vendor@example.test",
            subject="Test",
            snippet="Test",
            timestamp="2026-06-14T08:00:00+00:00",
            labels=None,
        )
        result = normalizer.normalize(raw)
        assert result.labels == []

    def test_none_internaldate(self, normalizer):
        raw = YahooRawRecord(
            uid="test_none_idate",
            sender="vendor@example.test",
            subject="Test",
            snippet="Test",
            timestamp="2026-06-14T08:00:00+00:00",
            internaldate=None,
        )
        result = normalizer.normalize(raw)
        assert isinstance(result, InboxEmail)

    def test_datetime_timestamp(self, normalizer):
        """Test handling of datetime object instead of string."""
        raw = YahooRawRecord(
            uid="test_dt",
            sender="vendor@example.test",
            subject="Test",
            snippet="Test",
            timestamp=datetime(2026, 6, 14, 8, 0, 0),
        )
        result = normalizer.normalize(raw)
        assert isinstance(result.timestamp, datetime)

    def test_malformed_timestamp_fallback(self, normalizer):
        """Bad timestamp should not crash."""
        raw = YahooRawRecord(
            uid="test_bad_ts",
            sender="vendor@example.test",
            subject="Test",
            snippet="Test",
            timestamp="not-a-date",
        )
        result = normalizer.normalize(raw)
        assert isinstance(result.timestamp, datetime)

    def test_empty_subject_and_snippet(self, normalizer):
        raw = YahooRawRecord(
            uid="test_empty",
            sender="vendor@example.test",
            subject="",
            snippet="",
            timestamp="2026-06-14T08:00:00+00:00",
        )
        result = normalizer.normalize(raw)
        assert isinstance(result, InboxEmail)

    def test_default_folder_is_inbox(self, normalizer):
        raw = YahooRawRecord(
            uid="test_default",
            sender="vendor@example.test",
            subject="Test",
            snippet="Test",
            timestamp="2026-06-14T08:00:00+00:00",
            # folder not specified → defaults to "INBOX"
        )
        result = normalizer.normalize(raw)
        assert "folder=INBOX" in result.source_ref

    def test_default_flags_is_empty_list(self, normalizer):
        raw = YahooRawRecord(
            uid="test_default_flags",
            sender="vendor@example.test",
            subject="Test",
            snippet="Test",
            timestamp="2026-06-14T08:00:00+00:00",
            # flags not specified → defaults to []
        )
        result = normalizer.normalize(raw)
        assert isinstance(result, InboxEmail)


# ── Integration tests ─────────────────────────────────────────────────────────


class TestYahooIntegration:
    """Integration tests combining normalization and filtering."""

    def test_normalize_then_filter_by_bucket(self, batch_normalizer, reference_date):
        """Normalize batch then filter by classification."""
        raw_list = [
            sample_yahoo_bill(),
            sample_yahoo_followup(),
            sample_yahoo_worth_checking(),
            sample_yahoo_fyi(),
            sample_yahoo_unclassified(),
        ]
        normalized = batch_normalizer.normalize_batch(raw_list, reference_date)
        
        bills = [e for e in normalized if e.bucket == BUCKET_BILL]
        followups = [e for e in normalized if e.bucket == BUCKET_FOLLOWUP]
        
        assert len(bills) == 1
        assert len(followups) == 1

    def test_clean_and_normalize_inbox_flow(self, batch_normalizer, reference_date):
        """Typical flow: get records, clean (filter spam/deleted), normalize."""
        raw_list = [
            sample_yahoo_bill(),
            sample_yahoo_spam(),
            sample_yahoo_trash(),
            sample_yahoo_followup(),
        ]
        
        # Clean first
        cleaned = batch_normalizer.filter_not_spam(raw_list)
        cleaned = batch_normalizer.filter_not_deleted(cleaned)
        assert len(cleaned) == 2
        
        # Then normalize
        normalized = batch_normalizer.normalize_batch(cleaned, reference_date)
        assert len(normalized) == 2
        assert all(e.source == "yahoo" for e in normalized)

    def test_all_synthetic_domains(self, batch_normalizer):
        """Verify all test records use synthetic domains."""
        test_records = [
            sample_yahoo_bill(),
            sample_yahoo_followup(),
            sample_yahoo_worth_checking(),
            sample_yahoo_fyi(),
            sample_yahoo_unclassified(),
            sample_yahoo_archived(),
            sample_yahoo_spam(),
            sample_yahoo_trash(),
        ]
        
        for raw in test_records:
            assert ".example" in raw.sender or ".test" in raw.sender, \
                f"Non-synthetic domain in {raw.sender}"

    def test_batch_dict_input_with_all_fields(self, batch_normalizer, reference_date):
        """Test batch processing with fully-populated dict inputs."""
        records_dict = [
            {
                "uid": "yahoo_full_001",
                "sender": "billing@fakebank.test",
                "subject": "Invoice due June 18",
                "snippet": "Amount: $100. Due by June 18.",
                "timestamp": "2026-06-14T08:00:00+00:00",
                "folder": "INBOX",
                "flags": ["\\Seen", "\\Flagged"],
                "internaldate": "14-Jun-2026 08:00:00 +0000",
                "yahoo_message_id": "yahoo123456",
                "labels": ["billing", "important"],
                "thread_key": "t_invoice",
                "source_ref": "manual-import",
            }
        ]
        
        results = batch_normalizer.normalize_batch(records_dict, reference_date)
        assert len(results) == 1
        result = results[0]
        
        assert result.id == "yahoo_full_001"
        assert result.source == "yahoo"
        assert result.bucket == BUCKET_BILL
        assert result.amount == 100.0
        assert "billing" in result.labels
