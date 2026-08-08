# tests/test_source_credibility.py
import src.tools.source_credibility as sc
from tests.conftest import FakeLLM


def _patch(monkeypatch, content: str):
    monkeypatch.setattr(sc, "get_llm", lambda temperature=0.0: FakeLLM(content))


# ─── parse path ──────────────────────────────────────────────────────────────

class TestJsonExtraction:
    def test_parses_plain_json(self, monkeypatch):
        payload = """{
          "source_known": true,
          "author_identifiable": false,
          "domain_age_signal": "established",
          "credibility_score": 0.8,
          "risk_contribution": 0.2,
          "explanation": "Known source."
        }"""
        _patch(monkeypatch, payload)
        out = sc.check_source_credibility("sample")
        assert out["source_known"] is True
        assert out["domain_age_signal"] == "established"
        assert out["credibility_score"] == 0.8

    def test_parses_fenced_json(self, monkeypatch):
        payload = """```json
        {
          "source_known": false,
          "author_identifiable": false,
          "domain_age_signal": "unknown",
          "credibility_score": 0.3,
          "risk_contribution": 0.7,
          "explanation": "Unclear source."
        }
        ```"""
        _patch(monkeypatch, payload)
        out = sc.check_source_credibility("sample")
        assert out["source_known"] is False
        assert out["risk_contribution"] == 0.7

    def test_parses_json_embedded_in_prose(self, monkeypatch):
        payload = 'Here is my assessment: {"source_known": true, "author_identifiable": true, "domain_age_signal": "established", "credibility_score": 0.9, "risk_contribution": 0.1, "explanation": "Reputable outlet."}'
        _patch(monkeypatch, payload)
        out = sc.check_source_credibility("sample")
        assert out["source_known"] is True
        assert out["explanation"] == "Reputable outlet."

    def test_extracts_first_object_when_multiple_fragments_in_prose(self, monkeypatch):
        # Greedy regex would span from first { to last }, producing invalid JSON.
        # raw_decode stops at the boundary of the first complete object.
        first = '{"source_known": true, "author_identifiable": true, "domain_age_signal": "established", "credibility_score": 0.9, "risk_contribution": 0.1, "explanation": "First."}'
        second = '{"source_known": false, "risk_contribution": 0.9, "explanation": "Second."}'
        payload = f"Option A: {first} Option B: {second}"
        _patch(monkeypatch, payload)
        out = sc.check_source_credibility("sample")
        assert out["explanation"] == "First."

    def test_parses_nested_json_object(self, monkeypatch):
        # Nested objects must not be truncated at the first inner }
        payload = '{"source_known": true, "author_identifiable": false, "domain_age_signal": "established", "credibility_score": 0.7, "risk_contribution": 0.3, "explanation": "Nested fine.", "meta": {"extra": 1}}'
        _patch(monkeypatch, payload)
        out = sc.check_source_credibility("sample")
        assert out["source_known"] is True
        assert out["domain_age_signal"] == "established"

    def test_returns_defaults_on_invalid_json(self, monkeypatch):
        _patch(monkeypatch, "not-json at all")
        out = sc.check_source_credibility("sample")
        assert out["source_known"] is False
        assert out["domain_age_signal"] == "unknown"
        assert out["risk_contribution"] == 0.7

    def test_returns_defaults_when_response_is_json_array(self, monkeypatch):
        _patch(monkeypatch, '[{"source_known": true}]')
        out = sc.check_source_credibility("sample")
        # array is not a dict — should fall back to defaults
        assert out["source_known"] is False


# ─── _sanitize edge cases ────────────────────────────────────────────────────

class TestSanitize:
    def _run(self, monkeypatch, payload_dict: dict) -> dict:
        import json
        _patch(monkeypatch, json.dumps(payload_dict))
        return sc.check_source_credibility("sample")

    def test_invalid_domain_age_signal_becomes_unknown(self, monkeypatch):
        out = self._run(monkeypatch, {
            "source_known": False,
            "author_identifiable": False,
            "domain_age_signal": "very_old",
            "credibility_score": 0.5,
            "risk_contribution": 0.5,
            "explanation": "x",
        })
        assert out["domain_age_signal"] == "unknown"

    def test_domain_age_signal_case_insensitive(self, monkeypatch):
        out = self._run(monkeypatch, {
            "source_known": False,
            "author_identifiable": False,
            "domain_age_signal": "ESTABLISHED",
            "credibility_score": 0.5,
            "risk_contribution": 0.5,
            "explanation": "x",
        })
        assert out["domain_age_signal"] == "established"

    def test_risk_contribution_clamped_above_one(self, monkeypatch):
        out = self._run(monkeypatch, {
            "source_known": False,
            "author_identifiable": False,
            "domain_age_signal": "unknown",
            "credibility_score": 0.5,
            "risk_contribution": 1.8,
            "explanation": "x",
        })
        assert out["risk_contribution"] == 1.0

    def test_credibility_score_clamped_below_zero(self, monkeypatch):
        out = self._run(monkeypatch, {
            "source_known": False,
            "author_identifiable": False,
            "domain_age_signal": "unknown",
            "credibility_score": -0.5,
            "risk_contribution": 0.5,
            "explanation": "x",
        })
        assert out["credibility_score"] == 0.0

    def test_empty_explanation_uses_fallback(self, monkeypatch):
        out = self._run(monkeypatch, {
            "source_known": False,
            "author_identifiable": False,
            "domain_age_signal": "unknown",
            "credibility_score": 0.5,
            "risk_contribution": 0.5,
            "explanation": "",
        })
        assert out["explanation"] == "Could not fully assess source credibility."

    def test_non_numeric_score_uses_fallback(self, monkeypatch):
        out = self._run(monkeypatch, {
            "source_known": False,
            "author_identifiable": False,
            "domain_age_signal": "unknown",
            "credibility_score": "high",
            "risk_contribution": 0.5,
            "explanation": "x",
        })
        assert out["credibility_score"] == 0.3  # default fallback


# ─── boolean coercion ────────────────────────────────────────────────────────

class TestBooleanCoercion:
    def _run(self, monkeypatch, source_known, author_identifiable) -> dict:
        import json
        _patch(monkeypatch, json.dumps({
            "source_known": source_known,
            "author_identifiable": author_identifiable,
            "domain_age_signal": "unknown",
            "credibility_score": 0.5,
            "risk_contribution": 0.5,
            "explanation": "test",
        }))
        return sc.check_source_credibility("sample")

    def test_json_true_bool(self, monkeypatch):
        out = self._run(monkeypatch, True, False)
        assert out["source_known"] is True
        assert out["author_identifiable"] is False

    def test_string_true_coerced_correctly(self, monkeypatch):
        out = self._run(monkeypatch, "true", "false")
        assert out["source_known"] is True
        assert out["author_identifiable"] is False

    def test_string_false_not_truthy(self, monkeypatch):
        # key regression: bool("false") == True, but _as_bool("false") == False
        out = self._run(monkeypatch, "false", "false")
        assert out["source_known"] is False
        assert out["author_identifiable"] is False

    def test_extended_truthy_values(self, monkeypatch):
        for truthy in ("1", "yes", "y", "YES", "True"):
            out = self._run(monkeypatch, truthy, "false")
            assert out["source_known"] is True, f"Expected True for {truthy!r}"

    def test_extended_falsy_values(self, monkeypatch):
        for falsy in ("0", "no", "n", "NO", "False"):
            out = self._run(monkeypatch, "true", falsy)
            assert out["author_identifiable"] is False, f"Expected False for {falsy!r}"

    def test_none_uses_fallback(self, monkeypatch):
        import json as _json
        _patch(monkeypatch, _json.dumps({
            "source_known": None,
            "author_identifiable": None,
            "domain_age_signal": "unknown",
            "credibility_score": 0.5,
            "risk_contribution": 0.5,
            "explanation": "test",
        }))
        out = sc.check_source_credibility("sample")
        # None → fallback values from _default_result()
        assert out["source_known"] is False
        assert out["author_identifiable"] is False
