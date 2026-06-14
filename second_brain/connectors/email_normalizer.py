"""
Email normalization and classification for Prebrief Batch 3.

Converts synthetic/raw email-like records into normalized InboxEmail schema.
Provides classification logic for bucket values (bill, followup, worth_checking, fyi, unclassified).
Extracts due-dates and amounts for bills/payment cases.

Policy:
- Offline, deterministic processing of synthetic fixtures only.
- No real inbox data, no live network calls.
- No PII in source or results.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Optional

from .schemas import InboxEmail


# ── Bucket definitions ────────────────────────────────────────────────────────

BUCKET_BILL = "bill"
BUCKET_FOLLOWUP = "followup"
BUCKET_WORTH_CHECKING = "worth_checking"
BUCKET_FYI = "fyi"
BUCKET_UNCLASSIFIED = "unclassified"

VALID_BUCKETS = {
    BUCKET_BILL,
    BUCKET_FOLLOWUP,
    BUCKET_WORTH_CHECKING,
    BUCKET_FYI,
    BUCKET_UNCLASSIFIED,
}


@dataclass
class RawEmailRecord:
    """Raw email-like record from any source (fixture, API, etc.)."""

    id: str
    sender: str
    subject: str
    snippet: str
    timestamp: str | datetime  # ISO string or datetime object
    labels: list[str] | None = None
    thread_key: str = ""
    source_ref: str = ""


class EmailNormalizer:
    """Normalize raw email records to InboxEmail schema with classification."""

    def __init__(self):
        """Initialize patterns for extraction."""
        # Amount patterns: $123.45, 123.45, etc.
        # Must be preceded by $ or 'amount' to avoid dates
        self._amount_pattern = re.compile(
            r"\$\d+(?:,\d{3})*(?:\.\d{2})?",
            re.IGNORECASE
        )
        self._amount_pattern_no_dollar = re.compile(
            r"(?:amount|balance|total)[:\s]+\d+(?:,\d{3})*(?:\.\d{2})?",
            re.IGNORECASE
        )
        
        # Due date patterns (simple heuristics)
        self._due_patterns = [
            r"due\s+(?:by\s+)?(?:on\s+)?([a-zA-Z]+\s+\d{1,2}|\w+day)",
            r"due\s+(?:by\s+)?(?:on\s+)?(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
            r"payment\s+(?:due\s+)?(?:by\s+)?(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
            r"by\s+(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
            r"deadline.*?(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
        ]
        
        # Bill/payment keywords
        self._bill_keywords = {
            "bill", "invoice", "statement", "payment", "charge",
            "due", "amount", "balance", "account", "subscription",
            "monthly", "annual", "fees", "interest", "credit card",
        }
        
        # Followup/action keywords
        self._action_keywords = {
            "follow up", "respond", "please respond", "please reply",
            "needs response", "action required", "reply", "confirm",
            "approve", "sign", "review", "feedback", "permission",
            "approve", "authorize", "submit",
        }
        
        # Worth checking keywords (informational but valuable)
        self._worth_checking_keywords = {
            "alert", "notification", "update", "change", "modified",
            "important", "note", "reminder", "schedule change",
            "status", "confirmation", "delivery", "shipment", "order",
        }

    def normalize(self, raw: RawEmailRecord, reference_date: date | None = None) -> InboxEmail:
        """
        Normalize a raw email record to InboxEmail schema.
        
        Args:
            raw: RawEmailRecord to normalize
            reference_date: Date to use for relative date extraction (defaults to today)
            
        Returns:
            Normalized InboxEmail object
        """
        if reference_date is None:
            reference_date = date.today()
        
        # Parse timestamp
        if isinstance(raw.timestamp, str):
            try:
                ts = datetime.fromisoformat(raw.timestamp.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                ts = datetime.now()
        else:
            ts = raw.timestamp
        
        # Classify bucket
        bucket = self._classify_bucket(raw.subject, raw.snippet)
        
        # Extract amount (for bills)
        amount = None
        if bucket == BUCKET_BILL:
            amount = self._extract_amount(raw.subject, raw.snippet)
        
        # Extract due date (for bills and followups)
        due_date = None
        if bucket in (BUCKET_BILL, BUCKET_FOLLOWUP):
            due_date = self._extract_due_date(raw.subject, raw.snippet, reference_date)
        
        # Calculate urgency (0-5)
        urgency = self._calculate_urgency(bucket, due_date, reference_date)
        
        # Confidence in classification
        confidence = self._calculate_confidence(bucket, raw.subject, raw.snippet)
        
        # Action required
        action_required = bucket in (BUCKET_BILL, BUCKET_FOLLOWUP)
        
        return InboxEmail(
            id=raw.id,
            source="normalized",
            sender=raw.sender,
            subject=raw.subject,
            timestamp=ts,
            snippet=raw.snippet,
            labels=raw.labels or [],
            bucket=bucket,
            due_date=due_date,
            amount=amount,
            urgency=urgency,
            confidence=confidence,
            action_required=action_required,
            thread_key=raw.thread_key,
            source_ref=raw.source_ref,
        )

    def _classify_bucket(self, subject: str, snippet: str) -> str:
        """
        Classify email into one of: bill, followup, worth_checking, fyi, unclassified.
        
        Classification priority:
        1. Bill/payment indicators
        2. Action/followup indicators
        3. Worth checking (informational updates)
        4. FYI (newsletters, general info)
        5. Unclassified (fallback)
        """
        combined = (subject + " " + snippet).lower()
        
        # Check for bill
        bill_score = sum(1 for kw in self._bill_keywords if kw in combined)
        if bill_score >= 2:
            return BUCKET_BILL
        
        # Check for followup/action
        action_score = sum(1 for kw in self._action_keywords if kw in combined)
        if action_score >= 1:
            return BUCKET_FOLLOWUP
        
        # Check for worth checking
        worth_score = sum(1 for kw in self._worth_checking_keywords if kw in combined)
        if worth_score >= 1:
            return BUCKET_WORTH_CHECKING
        
        # Check for FYI (newsletters, promotions, general info)
        fyi_keywords = {"newsletter", "promotion", "deal", "offer", "sale", "weekly"}
        fyi_score = sum(1 for kw in fyi_keywords if kw in combined)
        if fyi_score >= 1:
            return BUCKET_FYI
        
        return BUCKET_UNCLASSIFIED

    def _extract_amount(self, subject: str, snippet: str) -> Optional[float]:
        """Extract amount from subject or snippet for bills."""
        combined = subject + " " + snippet
        
        # First try with $ prefix
        matches = self._amount_pattern.findall(combined)
        if matches:
            amount_str = matches[0].replace("$", "").replace(",", "").strip()
            try:
                return float(amount_str)
            except ValueError:
                pass
        
        # Then try 'amount:' or 'balance:' patterns
        matches = self._amount_pattern_no_dollar.findall(combined)
        if matches:
            match_str = matches[0]
            # Extract numbers from the match
            numbers = re.findall(r"\d+(?:,\d{3})*(?:\.\d{2})?", match_str)
            if numbers:
                amount_str = numbers[0].replace(",", "")
                try:
                    return float(amount_str)
                except ValueError:
                    pass
        
        return None

    def _extract_due_date(
        self,
        subject: str,
        snippet: str,
        reference_date: date,
    ) -> Optional[date]:
        """
        Extract due date from subject/snippet.
        
        Returns relative date if found, None otherwise.
        Handles patterns like "June 18", "6/18", "by Friday", etc.
        """
        combined = subject + " " + snippet
        
        # Try numeric patterns first (more reliable)
        numeric_patterns = [
            r"(?:due\s+)?(?:by\s+)?(?:on\s+)?(\d{1,2}[-/]\d{1,2}(?:[-/]\d{2,4})?)",
            r"(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
        ]
        for pattern in numeric_patterns:
            matches = re.finditer(pattern, combined, re.IGNORECASE)
            for match in matches:
                date_str = match.group(1)
                parsed = self._parse_date_string(date_str, reference_date)
                if parsed:
                    return parsed
        
        # Try month names with optional year: "June 18, 2026" or "June 18 2026"
        month_pattern = r"([a-zA-Z]+\s+\d{1,2})(?:[,\s]+(\d{4}))?"
        matches = re.finditer(month_pattern, combined, re.IGNORECASE)
        for match in matches:
            date_str = match.group(1)
            year = match.group(2)
            if year:
                date_str = f"{date_str} {year}"
            parsed = self._parse_date_string(date_str, reference_date)
            if parsed:
                return parsed
        
        # Finally try day names
        day_pattern = r"(?:by\s+|on\s+)?(\w+day)"
        matches = re.finditer(day_pattern, combined, re.IGNORECASE)
        for match in matches:
            date_str = match.group(1)
            parsed = self._parse_date_string(date_str, reference_date)
            if parsed:
                return parsed
        
        return None

    def _parse_date_string(self, date_str: str, reference_date: date) -> Optional[date]:
        """
        Parse a date string relative to reference_date.
        
        Handles:
        - "June 18"
        - "June 18 2026"
        - "6/18"
        - "6-18-2026"
        - "6/18/2026"
        - Day names ("Monday", "Friday")
        """
        date_str = date_str.strip().lower()
        
        # Month + day + year: "June 18 2026", "June 18, 2026"
        month_day_year = re.match(
            r"([a-z]+)\s+(\d{1,2})\s+(\d{4})",
            date_str
        )
        if month_day_year:
            month_name, day, year = month_day_year.groups()
            return self._parse_month_day(month_name, int(day), reference_date, int(year))
        
        # Month + day: "June 18", "Jun 18"
        month_day = re.match(
            r"([a-z]+)\s+(\d{1,2})",
            date_str
        )
        if month_day:
            month_name, day = month_day.groups()
            return self._parse_month_day(month_name, int(day), reference_date)
        
        # Numeric: "6/18", "6-18", "6-18-2026", "6/18/2026"
        numeric = re.match(
            r"(\d{1,2})[-/](\d{1,2})(?:[-/](\d{2,4}))?",
            date_str
        )
        if numeric:
            parts = numeric.groups()
            month, day = int(parts[0]), int(parts[1])
            # Parse year if provided
            if parts[2]:
                year_str = parts[2]
                # Handle 2-digit years (00-99 -> 2000-2099)
                if len(year_str) == 2:
                    year = 2000 + int(year_str)
                else:
                    year = int(year_str)
            else:
                year = reference_date.year
            
            try:
                result = date(year, month, day)
                # If parsed date is in the past and no explicit year, try next year
                if parts[2] is None and result < reference_date:
                    result = date(year + 1, month, day)
                return result
            except ValueError:
                return None
        
        # Day name: "Monday", "Friday"
        day_name = re.match(r"(\w+day)", date_str)
        if day_name:
            return self._parse_day_name(day_name.group(1), reference_date)
        
        return None

    def _parse_month_day(self, month_name: str, day: int, reference_date: date, year: int | None = None) -> Optional[date]:
        """Parse 'Month DD' or 'Month DD YYYY' format."""
        months = {
            "jan": 1, "january": 1,
            "feb": 2, "february": 2,
            "mar": 3, "march": 3,
            "apr": 4, "april": 4,
            "may": 5,
            "jun": 6, "june": 6,
            "jul": 7, "july": 7,
            "aug": 8, "august": 8,
            "sep": 9, "september": 9,
            "oct": 10, "october": 10,
            "nov": 11, "november": 11,
            "dec": 12, "december": 12,
        }
        month_lower = month_name.lower()
        month = None
        for key, val in months.items():
            if key in month_lower:
                month = val
                break
        
        if not month:
            return None
        
        # Use provided year or reference year
        use_year = year if year is not None else reference_date.year
        
        try:
            result = date(use_year, month, day)
            # If no explicit year was provided and date is in past, try next year
            if year is None and result < reference_date:
                result = date(use_year + 1, month, day)
            return result
        except ValueError:
            return None

    def _parse_day_name(self, day_name: str, reference_date: date) -> Optional[date]:
        """Parse day name like 'Monday', 'Friday' → next occurrence."""
        day_map = {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        }
        day_lower = day_name.lower()
        target_day = None
        for key, val in day_map.items():
            if key in day_lower:
                target_day = val
                break
        
        if target_day is None:
            return None
        
        # Find next occurrence of this day
        current_day = reference_date.weekday()
        days_ahead = (target_day - current_day) % 7
        if days_ahead == 0:
            days_ahead = 7  # If today is the target day, use next week
        
        return reference_date + timedelta(days=days_ahead)

    def _calculate_urgency(
        self,
        bucket: str,
        due_date: Optional[date],
        reference_date: date,
    ) -> int:
        """
        Calculate urgency (0-5 scale).
        
        0: No urgency (FYI)
        1: Low (worth_checking, distant future)
        2: Medium (followup, bill due in 1-2 weeks)
        3: High (bill due in 3-7 days)
        4: Critical (bill due in 1-2 days)
        5: Overdue (bill due < today)
        """
        if bucket == BUCKET_FYI:
            return 0
        
        if bucket == BUCKET_WORTH_CHECKING:
            return 1
        
        if not due_date:
            # No due date
            if bucket == BUCKET_FOLLOWUP:
                return 2
            return 1
        
        days_until = (due_date - reference_date).days
        
        if days_until < 0:
            return 5  # Overdue
        elif days_until <= 2:
            return 4  # Critical
        elif days_until <= 7:
            return 3  # High
        elif days_until <= 14:
            return 2  # Medium
        else:
            return 1  # Low

    def _calculate_confidence(self, bucket: str, subject: str, snippet: str) -> float:
        """
        Calculate confidence in classification (0.0-1.0).
        
        Factors:
        - Multiple matching keywords
        - Explicit indicators (like amounts for bills)
        - Length/completeness of subject/snippet
        """
        combined = subject + " " + snippet
        
        # Base confidence by bucket
        base_confidence = {
            BUCKET_BILL: 0.85,
            BUCKET_FOLLOWUP: 0.80,
            BUCKET_WORTH_CHECKING: 0.75,
            BUCKET_FYI: 0.70,
            BUCKET_UNCLASSIFIED: 0.50,
        }.get(bucket, 0.50)
        
        # Boost for explicit amounts in bills
        if bucket == BUCKET_BILL:
            if "$" in combined or "amount" in combined.lower():
                base_confidence = min(0.99, base_confidence + 0.1)
        
        # Boost for action keywords in followups
        if bucket == BUCKET_FOLLOWUP:
            action_keywords = {"action required", "please", "respond", "follow up"}
            if any(kw in combined.lower() for kw in action_keywords):
                base_confidence = min(0.99, base_confidence + 0.1)
        
        return min(0.99, base_confidence)


class EmailNormalizerBatch:
    """Process multiple raw email records in batch."""
    
    def __init__(self):
        self.normalizer = EmailNormalizer()
    
    def normalize_batch(
        self,
        raw_records: list[RawEmailRecord] | list[dict[str, Any]],
        reference_date: date | None = None,
    ) -> list[InboxEmail]:
        """
        Normalize a batch of raw email records.
        
        Args:
            raw_records: List of RawEmailRecord or dicts
            reference_date: Reference date for relative date extraction
            
        Returns:
            List of normalized InboxEmail objects
        """
        if reference_date is None:
            reference_date = date.today()
        
        results = []
        for record in raw_records:
            # Convert dict to RawEmailRecord if needed
            if isinstance(record, dict):
                raw = RawEmailRecord(
                    id=record["id"],
                    sender=record["sender"],
                    subject=record["subject"],
                    snippet=record["snippet"],
                    timestamp=record.get("timestamp", ""),
                    labels=record.get("labels", []),
                    thread_key=record.get("thread_key", ""),
                    source_ref=record.get("source_ref", ""),
                )
            else:
                raw = record
            
            normalized = self.normalizer.normalize(raw, reference_date)
            results.append(normalized)
        
        return results
