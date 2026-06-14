"""
Yahoo email normalization adapter for Prebrief Batch 4.

Converts synthetic Yahoo-style email records into normalized InboxEmail schema.
Reuses Batch 3 email normalization logic (EmailNormalizer) with Yahoo-specific
metadata handling (UIDs, folders, flags, etc.).

Policy:
- Offline, deterministic processing of synthetic fixtures only.
- No real Yahoo data, no live IMAP access, no credentials.
- No PII in source or results.
- Reuses EmailNormalizer from Batch 3 to avoid duplication.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional

from .email_normalizer import EmailNormalizer, RawEmailRecord
from .schemas import InboxEmail


@dataclass
class YahooRawRecord:
    """
    Synthetic Yahoo-style email record.
    
    Represents data that might come from Yahoo Mail API or synthetic fixtures.
    Includes Yahoo-specific metadata (UID, folder, flags) plus standard email fields.
    """

    uid: str  # Unique identifier (Yahoo internal or synthetic)
    sender: str  # From address
    subject: str  # Subject line
    snippet: str  # Preview/body excerpt
    timestamp: str | datetime  # Received date (ISO string or datetime)
    
    # Yahoo-specific metadata
    folder: str = "INBOX"  # Folder name (INBOX, ARCHIVE, TRASH, etc.)
    flags: list[str] = field(default_factory=list)  # IMAP-like flags: ["\Seen", "\Flagged", ...]
    internaldate: Optional[str] = None  # Yahoo internal date metadata
    yahoo_message_id: Optional[str] = None  # Yahoo unique message ID
    
    # Standard email metadata
    labels: list[str] = field(default_factory=list)  # Yahoo labels/tags
    thread_key: str = ""  # Thread/conversation ID
    source_ref: str = ""  # Reference for tracking source


class YahooNormalizer:
    """
    Normalize Yahoo-style email records to InboxEmail schema.
    
    Reuses Batch 3 EmailNormalizer for classification and extraction logic.
    Focuses on Yahoo-specific metadata mapping and adapter logic.
    """

    def __init__(self):
        """Initialize with Batch 3 email normalizer."""
        self._email_normalizer = EmailNormalizer()

    def normalize(
        self,
        yahoo_record: YahooRawRecord,
        reference_date: date | None = None,
    ) -> InboxEmail:
        """
        Normalize a Yahoo record to InboxEmail schema.
        
        Args:
            yahoo_record: YahooRawRecord with Yahoo-specific metadata
            reference_date: Date for relative date extraction
            
        Returns:
            Normalized InboxEmail object with Yahoo source attribution
        """
        if reference_date is None:
            reference_date = date.today()

        # Convert YahooRawRecord to RawEmailRecord for Batch 3 normalizer
        raw_email = RawEmailRecord(
            id=yahoo_record.uid,
            sender=yahoo_record.sender,
            subject=yahoo_record.subject,
            snippet=yahoo_record.snippet,
            timestamp=yahoo_record.timestamp,
            labels=yahoo_record.labels or [],
            thread_key=yahoo_record.thread_key,
            source_ref=yahoo_record.source_ref,
        )

        # Use Batch 3 normalizer to classify and extract metadata
        normalized = self._email_normalizer.normalize(raw_email, reference_date)

        # Override source to indicate Yahoo origin
        normalized.source = "yahoo"

        # Preserve Yahoo-specific metadata in source_ref
        # Compact representation: "yahoo:folder=INBOX|flags=Seen,Flagged|internaldate=..."
        parts = [f"folder={yahoo_record.folder}"]
        if yahoo_record.flags:
            parts.append(f"flags={','.join(yahoo_record.flags)}")
        if yahoo_record.internaldate:
            parts.append(f"internaldate={yahoo_record.internaldate}")
        if yahoo_record.yahoo_message_id:
            parts.append(f"yahoo_message_id={yahoo_record.yahoo_message_id}")
        normalized.source_ref = "yahoo:" + "|".join(parts)

        return normalized

    def _is_read(self, flags: list[str]) -> bool:
        """Check if email is marked as read (has \\Seen flag)."""
        return any(flag.lower() == "\\seen" for flag in flags)

    def _is_flagged(self, flags: list[str]) -> bool:
        """Check if email is flagged/starred (has \\Flagged flag)."""
        return any(flag.lower() == "\\flagged" for flag in flags)

    def _is_deleted(self, flags: list[str]) -> bool:
        """Check if email is marked for deletion (has \\Deleted flag)."""
        return any(flag.lower() == "\\deleted" for flag in flags)

    def _is_in_trash(self, folder: str) -> bool:
        """Check if email is in trash-like folder."""
        trash_folders = {"TRASH", "[GMAIL]/TRASH", "DELETED", "[YAHOO]/TRASH"}
        return folder.upper() in trash_folders

    def _is_spam(self, folder: str) -> bool:
        """Check if email is in spam folder."""
        spam_folders = {"SPAM", "[GMAIL]/SPAM", "JUNK", "[YAHOO]/SPAM"}
        return folder.upper() in spam_folders


class YahooNormalizerBatch:
    """Process multiple Yahoo records in batch."""

    def __init__(self):
        """Initialize with Yahoo normalizer."""
        self._normalizer = YahooNormalizer()

    def normalize_batch(
        self,
        yahoo_records: list[YahooRawRecord] | list[dict[str, Any]],
        reference_date: date | None = None,
    ) -> list[InboxEmail]:
        """
        Normalize a batch of Yahoo records.
        
        Args:
            yahoo_records: List of YahooRawRecord or dicts
            reference_date: Reference date for relative date extraction
            
        Returns:
            List of normalized InboxEmail objects
        """
        if reference_date is None:
            reference_date = date.today()

        results = []
        for record in yahoo_records:
            # Convert dict to YahooRawRecord if needed
            if isinstance(record, dict):
                yahoo_raw = YahooRawRecord(
                    uid=record["uid"],
                    sender=record["sender"],
                    subject=record["subject"],
                    snippet=record["snippet"],
                    timestamp=record.get("timestamp", ""),
                    folder=record.get("folder", "INBOX"),
                    flags=record.get("flags", []),
                    internaldate=record.get("internaldate"),
                    yahoo_message_id=record.get("yahoo_message_id"),
                    labels=record.get("labels", []),
                    thread_key=record.get("thread_key", ""),
                    source_ref=record.get("source_ref", ""),
                )
            else:
                yahoo_raw = record

            normalized = self._normalizer.normalize(yahoo_raw, reference_date)
            results.append(normalized)

        return results

    def filter_by_folder(
        self,
        records: list[YahooRawRecord],
        folder: str,
    ) -> list[YahooRawRecord]:
        """Filter Yahoo records by folder."""
        return [r for r in records if r.folder == folder]

    def filter_by_flag(
        self,
        records: list[YahooRawRecord],
        flag: str,
    ) -> list[YahooRawRecord]:
        """Filter Yahoo records by flag (case-insensitive)."""
        flag_lower = flag.lower()
        return [r for r in records if any(f.lower() == flag_lower for f in r.flags)]

    def filter_unread(self, records: list[YahooRawRecord]) -> list[YahooRawRecord]:
        """Filter to only unread emails (missing \\Seen flag)."""
        return [
            r for r in records
            if not any(f.lower() == "\\seen" for f in r.flags)
        ]

    def filter_flagged(self, records: list[YahooRawRecord]) -> list[YahooRawRecord]:
        """Filter to only flagged/starred emails."""
        return [
            r for r in records
            if any(f.lower() == "\\flagged" for f in r.flags)
        ]

    def filter_not_deleted(
        self,
        records: list[YahooRawRecord],
    ) -> list[YahooRawRecord]:
        """Filter out deleted emails and emails in trash."""
        normalizer = YahooNormalizer()
        return [
            r for r in records
            if not normalizer._is_deleted(r.flags)
            and not normalizer._is_in_trash(r.folder)
        ]

    def filter_not_spam(
        self,
        records: list[YahooRawRecord],
    ) -> list[YahooRawRecord]:
        """Filter out spam and junk emails."""
        normalizer = YahooNormalizer()
        return [r for r in records if not normalizer._is_spam(r.folder)]

    def sort_by_timestamp(
        self,
        records: list[YahooRawRecord],
        reverse: bool = False,
    ) -> list[YahooRawRecord]:
        """Sort Yahoo records by timestamp."""
        def parse_ts(ts: str | datetime) -> datetime:
            if isinstance(ts, datetime):
                return ts
            try:
                return datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                return datetime.now()

        return sorted(records, key=lambda r: parse_ts(r.timestamp), reverse=reverse)
