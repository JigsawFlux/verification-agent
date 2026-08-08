# tests/test_privacy.py
import json
import os
from pathlib import Path

import pytest

from src.privacy import HistoryStorage, redact_pii


# ─── PII redaction ───────────────────────────────────────────────────────────

class TestRedactPii:
    def test_redacts_email(self):
        out = redact_pii("Contact us at support@example.co.uk for help")
        assert "[EMAIL]" in out
        assert "support@example.co.uk" not in out

    def test_redacts_uk_ni_number(self):
        out = redact_pii("Your NI number AB123456C has been verified.")
        assert "[NI_NUMBER]" in out
        assert "AB123456C" not in out

    def test_redacts_uk_phone_with_plus44(self):
        out = redact_pii("Call us on +44 7700 900123 now")
        assert "[PHONE]" in out
        assert "7700 900123" not in out

    def test_redacts_payment_card(self):
        out = redact_pii("Enter card 4111 1111 1111 1111 to proceed")
        assert "[CARD_NUMBER]" in out
        assert "4111 1111 1111 1111" not in out

    def test_redacts_multiple_pii_in_one_string(self):
        text = "Send NI AB123456C and email me at user@test.com"
        out = redact_pii(text)
        assert "[NI_NUMBER]" in out
        assert "[EMAIL]" in out
        assert "AB123456C" not in out
        assert "user@test.com" not in out

    def test_no_change_on_clean_text(self):
        text = "The quick brown fox jumps over the lazy dog."
        assert redact_pii(text) == text

    def test_redaction_is_idempotent(self):
        text = "Email: user@example.com"
        once = redact_pii(text)
        twice = redact_pii(once)
        assert once == twice


# ─── HistoryStorage — consent off ────────────────────────────────────────────

class TestHistoryStorageConsentOff:
    def test_save_returns_false_when_consent_false(self, tmp_path):
        storage = HistoryStorage(consent=False, history_dir=tmp_path / "history")
        result = storage.save("run-abc-123", {"risk_level": "Low"})
        assert result is False

    def test_no_file_written_when_consent_false(self, tmp_path):
        history_dir = tmp_path / "history"
        storage = HistoryStorage(consent=False, history_dir=history_dir)
        storage.save("run-xyz", {"risk_level": "High"})
        assert not history_dir.exists() or len(list(history_dir.glob("*.json"))) == 0


# ─── HistoryStorage — consent on ─────────────────────────────────────────────

class TestHistoryStorageConsentOn:
    def test_save_returns_true_and_writes_file(self, tmp_path):
        storage = HistoryStorage(consent=True, history_dir=tmp_path / "history")
        result = storage.save("run-abc-123456", {"risk_level": "Medium", "confidence": 0.75})
        assert result is True
        files = list((tmp_path / "history").glob("*.json"))
        assert len(files) == 1

    def test_saved_file_contains_run_id(self, tmp_path):
        storage = HistoryStorage(consent=True, history_dir=tmp_path / "history")
        storage.save("run-deadbeef-cafe", {"risk_level": "High"})
        files = list((tmp_path / "history").glob("*.json"))
        payload = json.loads(files[0].read_text())
        assert payload["run_id"] == "run-deadbeef-cafe"

    def test_multiple_saves_create_multiple_files(self, tmp_path):
        storage = HistoryStorage(consent=True, history_dir=tmp_path / "history")
        storage.save("run-001", {"risk_level": "Low"})
        storage.save("run-002", {"risk_level": "High"})
        files = list((tmp_path / "history").glob("*.json"))
        assert len(files) == 2


# ─── HistoryStorage — cleanup ────────────────────────────────────────────────

class TestHistoryStorageCleanup:
    def test_cleanup_returns_zero_when_dir_absent(self, tmp_path):
        storage = HistoryStorage(consent=True, history_dir=tmp_path / "nonexistent")
        assert storage.cleanup() == 0

    def test_cleanup_removes_old_files(self, tmp_path):
        import time

        history_dir = tmp_path / "history"
        history_dir.mkdir()

        old_file = history_dir / "20200101_000000_oldrun.json"
        old_file.write_text('{"run_id": "old"}')
        # Back-date modification time to 100 days ago
        old_mtime = time.time() - (100 * 86400)
        os.utime(old_file, (old_mtime, old_mtime))

        recent_file = history_dir / "20991231_000000_newrun.json"
        recent_file.write_text('{"run_id": "new"}')

        storage = HistoryStorage(consent=True, history_dir=history_dir, retention_days=30)
        removed = storage.cleanup()

        assert removed == 1
        assert not old_file.exists()
        assert recent_file.exists()
