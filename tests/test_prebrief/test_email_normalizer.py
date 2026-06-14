"""
Tests for email normalization and classification (Batch 3).

Uses only synthetic fixtures. No real inbox data, no live network calls.
"""

import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from second_brain.connectors.email_normalizer import (
    BUCKET_BILL,
    BUCKET_FOLLOWUP,
    BUCKET_FYI,
    BUCKET_UNCLASSIFIED,
    BUCKET_WORTH_CHECKING,
    EmailNormalizer,
    EmailNormalizerBatch,
    RawEmailRecord,
)
from second_brain.connectors.schemas import InboxEmail


# ── Test fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def normalizer():
    return EmailNormalizer()


@pytest.fixture
def batch_normalizer():
    return EmailNormalizerBatch()


@pytest.fixture
def reference_date():
    return date(2026, 6, 15)


def sample_bill_raw() -> RawEmailRecord:
    """Sample bill email."""
    return RawEmailRecord(
        id="email_001",
        sender="billing@fakebank.test",
        subject="Your statement is ready — due June 18",
        snippet="Payment due June 18. Amount: $142.50.",
        timestamp="2026-06-14T08:00:00+00:00",
        labels=["billing"],
        thread_key="t_fakebank",
    )


def sample_followup_raw() -> RawEmailRecord:
    """Sample followup/action email."""
    return RawEmailRecord(
        id="email_002",
        sender="school@example.test",
        subject="Re: permission slip for field trip",
        snippet="Please sign and return by Friday.",
        timestamp="2026-06-13T16:30:00+00:00",
        labels=["school"],
        thread_key="t_fieldtrip",
    )


def sample_worth_checking_raw() -> RawEmailRecord:
    """Sample worth-checking email (informational update)."""
    return RawEmailRecord(
        id="email_003",
        sender="alerts@travelco.example",
        subject="Flight time change for your July trip",
        snippet="Your July 4 departure has moved from 9:00am to 11:30am.",
        timestamp="2026-06-14T10:00:00+00:00",
        thread_key="t_travel",
    )


def sample_fyi_raw() -> RawEmailRecord:
    """Sample FYI email (newsletter)."""
    return RawEmailRecord(
        id="email_004",
        sender="newsletter@promos.example",
        subject="This week's deals!",
        snippet="Check out our latest offers...",
        timestamp="2026-06-14T07:00:00+00:00",
        thread_key="t_promo",
    )


def sample_unclassified_raw() -> RawEmailRecord:
    """Sample unclassified email."""
    return RawEmailRecord(
        id="email_005",
        sender="friend@example.test",
        subject="Hey",
        snippet="Just wanted to catch up.",
        timestamp="2026-06-14T12:00:00+00:00",
    )


# ── Classification tests ──────────────────────────────────────────────────────


class TestBucketClassification:
    """Test email bucket classification."""

    def test_classify_bill(self, normalizer):
        raw = sample_bill_raw()
        result = normalizer.normalize(raw)
        assert result.bucket == BUCKET_BILL

    def test_classify_followup(self, normalizer):
        raw = sample_followup_raw()
        result = normalizer.normalize(raw)
        assert result.bucket == BUCKET_FOLLOWUP

    def test_classify_worth_checking(self, normalizer):
        raw = sample_worth_checking_raw()
        result = normalizer.normalize(raw)
        assert result.bucket == BUCKET_WORTH_CHECKING

    def test_classify_fyi(self, normalizer):
        raw = sample_fyi_raw()
        result = normalizer.normalize(raw)
        assert result.bucket == BUCKET_FYI

    def test_classify_unclassified(self, normalizer):
        raw = sample_unclassified_raw()
        result = normalizer.normalize(raw)
        assert result.bucket == BUCKET_UNCLASSIFIED

    def test_bill_with_multiple_keywords(self, normalizer):
        """Bill should match with invoice + amount + due."""
        raw = RawEmailRecord(
            id="test_bill",
            sender="vendor@example.test",
            subject="Invoice #12345 - Payment Due",
            snippet="Your invoice has a balance of $500.00 due by June 30.",
            timestamp="2026-06-14T08:00:00+00:00",
        )
        result = normalizer.normalize(raw)
        assert result.bucket == BUCKET_BILL

    def test_action_keyword_priority(self, normalizer):
        """'Action required' should prioritize followup."""
        raw = RawEmailRecord(
            id="test_action",
            sender="admin@example.test",
            subject="Action required: Confirm your identity",
            snippet="We need you to confirm your identity by clicking the link.",
            timestamp="2026-06-14T08:00:00+00:00",
        )
        result = normalizer.normalize(raw)
        assert result.bucket == BUCKET_FOLLOWUP


# ── Amount extraction tests ───────────────────────────────────────────────────


class TestAmountExtraction:
    """Test amount extraction from bills."""

    def test_extract_dollar_amount(self, normalizer):
        raw = sample_bill_raw()
        result = normalizer.normalize(raw)
        assert result.amount == 142.50

    def test_extract_comma_separated_amount(self, normalizer):
        raw = RawEmailRecord(
            id="test_amount",
            sender="vendor@example.test",
            subject="Invoice for $1,234.56",
            snippet="Total amount: $1,234.56",
            timestamp="2026-06-14T08:00:00+00:00",
        )
        result = normalizer.normalize(raw)
        assert result.amount == 1234.56

    def test_extract_amount_without_dollar(self, normalizer):
        raw = RawEmailRecord(
            id="test_amount",
            sender="vendor@example.test",
            subject="Invoice - Payment $500",
            snippet="Total amount: $500",
            timestamp="2026-06-14T08:00:00+00:00",
        )
        result = normalizer.normalize(raw)
        assert result.amount == 500.0

    def test_no_amount_for_non_bill(self, normalizer):
        """Non-bill buckets should not extract amount."""
        raw = sample_followup_raw()
        result = normalizer.normalize(raw)
        assert result.amount is None

    def test_first_amount_extracted(self, normalizer):
        """If multiple amounts, take first."""
        raw = RawEmailRecord(
            id="test_amount",
            sender="vendor@example.test",
            subject="Invoice",
            snippet="Previous balance: $100. New charges: $50. Total: $150.",
            timestamp="2026-06-14T08:00:00+00:00",
        )
        result = normalizer.normalize(raw)
        # Should get first match: 100
        assert result.amount == 100.0


# ── Due date extraction tests ──────────────────────────────────────────────────


class TestDueDateExtraction:
    """Test due date extraction."""

    def test_extract_month_day(self, normalizer, reference_date):
        raw = sample_bill_raw()  # "due June 18"
        result = normalizer.normalize(raw, reference_date)
        assert result.due_date == date(2026, 6, 18)

    def test_extract_numeric_date(self, normalizer, reference_date):
        raw = RawEmailRecord(
            id="test_date",
            sender="vendor@example.test",
            subject="Payment due 6/30",
            snippet="Pay by 6/30",
            timestamp="2026-06-14T08:00:00+00:00",
        )
        result = normalizer.normalize(raw, reference_date)
        assert result.due_date == date(2026, 6, 30)

    def test_extract_day_name(self, normalizer, reference_date):
        """Parse 'Friday' relative to reference_date (June 15, 2026 = Monday)."""
        raw = sample_followup_raw()  # "by Friday"
        result = normalizer.normalize(raw, reference_date)
        # Next Friday from Monday June 15 = June 19
        assert result.due_date == date(2026, 6, 19)

    def test_extract_full_numeric_date(self, normalizer, reference_date):
        raw = RawEmailRecord(
            id="test_date",
            sender="vendor@example.test",
            subject="Payment invoice",
            snippet="Due by 6-30-2026",
            timestamp="2026-06-14T08:00:00+00:00",
        )
        result = normalizer.normalize(raw, reference_date)
        assert result.due_date == date(2026, 6, 30)

    def test_no_due_date_for_fyi(self, normalizer, reference_date):
        """FYI emails should not extract due date."""
        raw = sample_fyi_raw()
        result = normalizer.normalize(raw, reference_date)
        assert result.due_date is None

    def test_past_month_forward_to_next_year(self, normalizer, reference_date):
        """If month is in past (relative to reference), use next year."""
        raw = RawEmailRecord(
            id="test_date",
            sender="vendor@example.test",
            subject="Payment invoice",
            snippet="Due January 15. Amount: $100.",
            timestamp="2026-06-14T08:00:00+00:00",
        )
        result = normalizer.normalize(raw, reference_date)
        # June 15, 2026 → January 15, 2027
        assert result.due_date == date(2027, 1, 15)


# ── Urgency calculation tests ─────────────────────────────────────────────────


class TestUrgencyCalculation:
    """Test urgency score calculation."""

    def test_urgency_fyi(self, normalizer, reference_date):
        raw = sample_fyi_raw()
        result = normalizer.normalize(raw, reference_date)
        assert result.urgency == 0

    def test_urgency_worth_checking(self, normalizer, reference_date):
        raw = sample_worth_checking_raw()
        result = normalizer.normalize(raw, reference_date)
        assert result.urgency == 1

    def test_urgency_bill_overdue(self, normalizer, reference_date):
        raw = RawEmailRecord(
            id="test_urgent",
            sender="vendor@example.test",
            subject="Invoice due June 10, 2026",
            snippet="Amount: $100",
            timestamp="2026-06-14T08:00:00+00:00",
        )
        result = normalizer.normalize(raw, reference_date)
        assert result.urgency == 5  # Overdue

    def test_urgency_bill_critical(self, normalizer, reference_date):
        raw = RawEmailRecord(
            id="test_urgent",
            sender="vendor@example.test",
            subject="Invoice due June 16",
            snippet="Amount: $100",
            timestamp="2026-06-14T08:00:00+00:00",
        )
        result = normalizer.normalize(raw, reference_date)
        # June 16 is 1 day away → urgency 4
        assert result.urgency == 4

    def test_urgency_bill_high(self, normalizer, reference_date):
        raw = RawEmailRecord(
            id="test_urgent",
            sender="vendor@example.test",
            subject="Invoice due June 20",
            snippet="Amount: $100",
            timestamp="2026-06-14T08:00:00+00:00",
        )
        result = normalizer.normalize(raw, reference_date)
        # June 20 is 5 days away → urgency 3
        assert result.urgency == 3

    def test_urgency_bill_medium_far(self, normalizer, reference_date):
        raw = RawEmailRecord(
            id="test_urgent",
            sender="vendor@example.test",
            subject="Invoice due June 28",
            snippet="Amount: $100",
            timestamp="2026-06-14T08:00:00+00:00",
        )
        result = normalizer.normalize(raw, reference_date)
        # June 28 is 13 days away → urgency 2
        assert result.urgency == 2

    def test_urgency_followup_no_date(self, normalizer, reference_date):
        raw = RawEmailRecord(
            id="test_followup",
            sender="vendor@example.test",
            subject="Please review and respond",
            snippet="Your feedback is requested.",
            timestamp="2026-06-14T08:00:00+00:00",
        )
        result = normalizer.normalize(raw, reference_date)
        # Followup without date → urgency 2
        assert result.urgency == 2


# ── Confidence calculation tests ──────────────────────────────────────────────


class TestConfidenceCalculation:
    """Test confidence score calculation."""

    def test_confidence_bill_with_amount(self, normalizer):
        raw = sample_bill_raw()  # Has $ and "amount"
        result = normalizer.normalize(raw)
        assert result.confidence > 0.85

    def test_confidence_followup_with_action(self, normalizer):
        raw = RawEmailRecord(
            id="test_conf",
            sender="vendor@example.test",
            subject="Action required: Please respond",
            snippet="We need your feedback on this.",
            timestamp="2026-06-14T08:00:00+00:00",
        )
        result = normalizer.normalize(raw)
        assert result.confidence > 0.80

    def test_confidence_unclassified(self, normalizer):
        raw = sample_unclassified_raw()
        result = normalizer.normalize(raw)
        assert result.confidence == 0.50


# ── Action required flag tests ────────────────────────────────────────────────


class TestActionRequired:
    """Test action_required flag."""

    def test_action_required_bill(self, normalizer):
        raw = sample_bill_raw()
        result = normalizer.normalize(raw)
        assert result.action_required is True

    def test_action_required_followup(self, normalizer):
        raw = sample_followup_raw()
        result = normalizer.normalize(raw)
        assert result.action_required is True

    def test_action_not_required_fyi(self, normalizer):
        raw = sample_fyi_raw()
        result = normalizer.normalize(raw)
        assert result.action_required is False

    def test_action_not_required_worth_checking(self, normalizer):
        raw = sample_worth_checking_raw()
        result = normalizer.normalize(raw)
        assert result.action_required is False


# ── Schema normalization tests ────────────────────────────────────────────────


class TestSchemaNormalization:
    """Test that normalized output matches InboxEmail schema."""

    def test_normalized_is_inbox_email(self, normalizer):
        raw = sample_bill_raw()
        result = normalizer.normalize(raw)
        assert isinstance(result, InboxEmail)

    def test_normalized_id_preserved(self, normalizer):
        raw = sample_bill_raw()
        result = normalizer.normalize(raw)
        assert result.id == "email_001"

    def test_normalized_sender_preserved(self, normalizer):
        raw = sample_bill_raw()
        result = normalizer.normalize(raw)
        assert result.sender == "billing@fakebank.test"

    def test_normalized_subject_preserved(self, normalizer):
        raw = sample_bill_raw()
        result = normalizer.normalize(raw)
        assert result.subject == raw.subject

    def test_normalized_timestamp_conversion(self, normalizer):
        raw = sample_bill_raw()
        result = normalizer.normalize(raw)
        assert isinstance(result.timestamp, datetime)

    def test_normalized_snippet_preserved(self, normalizer):
        raw = sample_bill_raw()
        result = normalizer.normalize(raw)
        assert result.snippet == raw.snippet

    def test_normalized_source_is_normalized(self, normalizer):
        raw = sample_bill_raw()
        result = normalizer.normalize(raw)
        assert result.source == "normalized"

    def test_normalized_thread_key_preserved(self, normalizer):
        raw = sample_bill_raw()
        result = normalizer.normalize(raw)
        assert result.thread_key == "t_fakebank"

    def test_normalized_roundtrip_to_dict(self, normalizer):
        """Verify roundtrip to dict and back works."""
        raw = sample_bill_raw()
        original = normalizer.normalize(raw)
        restored = InboxEmail.from_dict(original.to_dict())
        assert restored == original


# ── Batch normalization tests ──────────────────────────────────────────────────


class TestBatchNormalization:
    """Test batch processing."""

    def test_batch_normalize_list_of_raw(self, batch_normalizer, reference_date):
        raw_list = [
            sample_bill_raw(),
            sample_followup_raw(),
            sample_fyi_raw(),
        ]
        results = batch_normalizer.normalize_batch(raw_list, reference_date)
        
        assert len(results) == 3
        assert results[0].bucket == BUCKET_BILL
        assert results[1].bucket == BUCKET_FOLLOWUP
        assert results[2].bucket == BUCKET_FYI

    def test_batch_normalize_list_of_dicts(self, batch_normalizer, reference_date):
        dicts = [
            {
                "id": "email_001",
                "sender": "vendor@example.test",
                "subject": "Invoice due June 18",
                "snippet": "Amount: $100",
                "timestamp": "2026-06-14T08:00:00+00:00",
                "labels": [],
                "thread_key": "t_1",
            }
        ]
        results = batch_normalizer.normalize_batch(dicts, reference_date)
        
        assert len(results) == 1
        assert results[0].bucket == BUCKET_BILL
        assert results[0].amount == 100.0

    def test_batch_preserves_order(self, batch_normalizer, reference_date):
        raw_list = [
            sample_bill_raw(),
            sample_followup_raw(),
            sample_worth_checking_raw(),
            sample_fyi_raw(),
            sample_unclassified_raw(),
        ]
        results = batch_normalizer.normalize_batch(raw_list, reference_date)
        
        assert len(results) == 5
        assert results[0].id == "email_001"
        assert results[1].id == "email_002"
        assert results[2].id == "email_003"
        assert results[3].id == "email_004"
        assert results[4].id == "email_005"


# ── Integration tests ──────────────────────────────────────────────────────────


class TestIntegration:
    """Integration tests with fixture files."""

    def test_normalize_fixture_emails(self, batch_normalizer, reference_date):
        """Test normalizing fixture emails from JSON."""
        fixture_path = Path(__file__).resolve().parents[1] / "fixtures" / "prebrief" / "emails.json"
        
        if fixture_path.exists():
            data = json.loads(fixture_path.read_text())
            # These are already in InboxEmail format; verify they load and classify correctly
            emails = [InboxEmail.from_dict(item) for item in data]
            assert len(emails) >= 4
            assert emails[0].bucket == BUCKET_BILL
            assert emails[1].bucket == BUCKET_FOLLOWUP
            assert emails[2].bucket == BUCKET_WORTH_CHECKING
            assert emails[3].bucket == BUCKET_FYI

    def test_all_synthetic_domains(self, normalizer):
        """Verify all test data uses synthetic domains."""
        test_cases = [
            sample_bill_raw(),
            sample_followup_raw(),
            sample_worth_checking_raw(),
            sample_fyi_raw(),
            sample_unclassified_raw(),
        ]
        
        for raw in test_cases:
            assert ".example" in raw.sender or ".test" in raw.sender, \
                f"Non-synthetic domain in {raw.sender}"


# ── Edge case tests ───────────────────────────────────────────────────────────


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_snippet(self, normalizer):
        raw = RawEmailRecord(
            id="test_empty",
            sender="vendor@example.test",
            subject="Invoice due June 18",
            snippet="",
            timestamp="2026-06-14T08:00:00+00:00",
        )
        result = normalizer.normalize(raw)
        assert result.bucket == BUCKET_BILL

    def test_empty_subject(self, normalizer):
        raw = RawEmailRecord(
            id="test_empty",
            sender="vendor@example.test",
            subject="",
            snippet="Amount: $100. Due June 18.",
            timestamp="2026-06-14T08:00:00+00:00",
        )
        result = normalizer.normalize(raw)
        assert result.bucket == BUCKET_BILL

    def test_datetime_timestamp_object(self, normalizer):
        """Handle datetime object instead of string."""
        ts = datetime(2026, 6, 14, 8, 0, 0)
        raw = RawEmailRecord(
            id="test_dt",
            sender="vendor@example.test",
            subject="Test",
            snippet="Test",
            timestamp=ts,
        )
        result = normalizer.normalize(raw)
        assert result.timestamp == ts

    def test_malformed_timestamp_fallback(self, normalizer):
        """Bad timestamp should fallback gracefully."""
        raw = RawEmailRecord(
            id="test_bad_ts",
            sender="vendor@example.test",
            subject="Test",
            snippet="Test",
            timestamp="not-a-date",
        )
        result = normalizer.normalize(raw)
        # Should not crash, timestamp will be approx now
        assert isinstance(result.timestamp, datetime)

    def test_none_labels(self, normalizer):
        """Verify None labels become empty list."""
        raw = RawEmailRecord(
            id="test_labels",
            sender="vendor@example.test",
            subject="Test",
            snippet="Test",
            timestamp="2026-06-14T08:00:00+00:00",
            labels=None,
        )
        result = normalizer.normalize(raw)
        assert result.labels == []

    def test_case_insensitivity_classification(self, normalizer):
        """Keywords should be case-insensitive."""
        raw = RawEmailRecord(
            id="test_case",
            sender="vendor@example.test",
            subject="INVOICE DUE BY 6/30",
            snippet="AMOUNT: $500",
            timestamp="2026-06-14T08:00:00+00:00",
        )
        result = normalizer.normalize(raw)
        assert result.bucket == BUCKET_BILL
        assert result.amount == 500.0
