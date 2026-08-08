# src/privacy.py
"""
PII redaction and consent-gated history storage.

HISTORY_CONSENT defaults to false — do not enable until the redaction
pipeline has been validated against your data classification policy.
"""
import json
import logging
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
# PII redaction patterns (UK-centric for MVP)
# -------------------------------------------------------------------
_PII_PATTERNS: list[tuple[re.Pattern, str]] = [
    # UK National Insurance number  e.g. AB123456C
    (re.compile(r"\b[A-Z]{2}\d{6}[A-D]?\b"), "[NI_NUMBER]"),
    # Payment card — 4 groups of 4 digits, optional spaces/dashes
    (re.compile(r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b"), "[CARD_NUMBER]"),
    # Email address
    (re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"), "[EMAIL]"),
    # UK phone numbers: +44 or 0 prefix; (?<!\w) used instead of \b because + is not a word char
    (re.compile(r"(?<!\w)(?:\+44\s?|0)(?:\d[\s\-]?){9,10}(?!\d)"), "[PHONE]"),
    # UK 8-digit bank account numbers (standalone — not inside card patterns)
    (re.compile(r"(?<!\d)\d{8}(?!\d)"), "[ACCOUNT_NUMBER]"),
]


def redact_pii(text: str) -> str:
    """Replace known PII patterns with labelled placeholders."""
    for pattern, placeholder in _PII_PATTERNS:
        text = pattern.sub(placeholder, text)
    return text


# -------------------------------------------------------------------
# Consent-gated history storage
# -------------------------------------------------------------------
_ENV_CONSENT = os.environ.get("HISTORY_CONSENT", "false").strip().lower()
_DEFAULT_CONSENT = _ENV_CONSENT in ("true", "1", "yes")
_DEFAULT_RETENTION_DAYS = int(os.environ.get("HISTORY_RETENTION_DAYS", "30"))
_DEFAULT_HISTORY_DIR = Path(os.environ.get("HISTORY_DIR", "data/history"))


class HistoryStorage:
    """
    Saves per-run records to disk only when consent is given.

    The caller is responsible for redacting PII from any fields before
    passing the record to save().
    """

    def __init__(
        self,
        consent: Optional[bool] = None,
        retention_days: Optional[int] = None,
        history_dir: Optional[Path] = None,
    ):
        self._consent = consent if consent is not None else _DEFAULT_CONSENT
        self._retention_days = retention_days if retention_days is not None else _DEFAULT_RETENTION_DAYS
        self._dir = history_dir if history_dir is not None else _DEFAULT_HISTORY_DIR

    def save(self, run_id: str, record: dict) -> bool:
        """
        Write record to disk.  Returns True if saved, False if consent is off.
        """
        if not self._consent:
            logger.debug("History save skipped: HISTORY_CONSENT=false")
            return False

        self._dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        path = self._dir / f"{ts}_{run_id[:8]}.json"
        payload = {"run_id": run_id, "timestamp": ts, **record}
        try:
            path.write_text(json.dumps(payload, indent=2, default=str))
            logger.debug("History saved: %s", path.name)
            return True
        except Exception as exc:
            logger.warning("History save failed: %s", exc)
            return False

    def cleanup(self) -> int:
        """Delete records older than retention_days. Returns count of files removed."""
        if not self._dir.exists():
            return 0

        cutoff = datetime.utcnow() - timedelta(days=self._retention_days)
        removed = 0
        for f in self._dir.glob("*.json"):
            try:
                mtime = datetime.utcfromtimestamp(f.stat().st_mtime)
                if mtime < cutoff:
                    f.unlink()
                    removed += 1
            except Exception as exc:
                logger.warning("Could not remove %s: %s", f.name, exc)
        return removed
