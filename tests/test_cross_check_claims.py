# tests/test_cross_check_claims.py
import json
import src.tools.cross_check as cc
from tests.conftest import FakeLLM


def _patch(monkeypatch, content: str):
    monkeypatch.setattr(cc, "get_llm", lambda temperature=0.0: FakeLLM(content))


# ─── JSON extraction ─────────────────────────────────────────────────────────

class TestJsonExtraction:
    def test_parses_plain_json(self, monkeypatch):
        payload = json.dumps({
            "claim_supported": True, "conflicting_sources": False,
            "date_context_ok": True, "evidence_quality": "strong",
            "consistency_score": 0.9, "risk_contribution": 0.1,
            "explanation": "Claims are well supported.",
        })
        _patch(monkeypatch, payload)
        out = cc.cross_check_claims("sample")
        assert out["claim_supported"] is True
        assert out["evidence_quality"] == "strong"

    def test_parses_fenced_json(self, monkeypatch):
        body = json.dumps({
            "claim_supported": False, "conflicting_sources": True,
            "date_context_ok": True, "evidence_quality": "misleading",
            "consistency_score": 0.2, "risk_contribution": 0.8,
            "explanation": "Multiple conflicts found.",
        })
        _patch(monkeypatch, f"```json\n{body}\n```")
        out = cc.cross_check_claims("sample")
        assert out["evidence_quality"] == "misleading"
        assert out["risk_contribution"] == 0.8

    def test_parses_json_embedded_in_prose(self, monkeypatch):
        inner = json.dumps({
            "claim_supported": False, "conflicting_sources": False,
            "date_context_ok": False, "evidence_quality": "insufficient",
            "consistency_score": 0.4, "risk_contribution": 0.6,
            "explanation": "Content is too vague.",
        })
        _patch(monkeypatch, f"Here is the result: {inner}")
        out = cc.cross_check_claims("sample")
        assert out["explanation"] == "Content is too vague."

    def test_extracts_first_object_when_multiple_fragments_in_prose(self, monkeypatch):
        first = json.dumps({
            "claim_supported": True, "conflicting_sources": False,
            "date_context_ok": True, "evidence_quality": "strong",
            "consistency_score": 0.85, "risk_contribution": 0.15,
            "explanation": "First result.",
        })
        second = json.dumps({
            "claim_supported": False, "conflicting_sources": True,
            "date_context_ok": False, "evidence_quality": "weak",
            "consistency_score": 0.3, "risk_contribution": 0.7,
            "explanation": "Second result.",
        })
        _patch(monkeypatch, f"Option A: {first} Option B: {second}")
        out = cc.cross_check_claims("sample")
        assert out["explanation"] == "First result."

    def test_returns_defaults_on_invalid_json(self, monkeypatch):
        _patch(monkeypatch, "not-json at all")
        out = cc.cross_check_claims("sample")
        assert out["claim_supported"] is False
        assert out["evidence_quality"] == "insufficient"

    def test_returns_defaults_when_response_is_json_array(self, monkeypatch):
        _patch(monkeypatch, '[{"claim_supported": true}]')
        out = cc.cross_check_claims("sample")
        assert out["claim_supported"] is False


# ─── _sanitize edge cases ────────────────────────────────────────────────────

class TestSanitize:
    def _run(self, monkeypatch, payload: dict) -> dict:
        _patch(monkeypatch, json.dumps(payload))
        return cc.cross_check_claims("sample")

    def _base(self, **overrides) -> dict:
        base = {
            "claim_supported": False, "conflicting_sources": False,
            "date_context_ok": True, "evidence_quality": "insufficient",
            "consistency_score": 0.4, "risk_contribution": 0.6,
            "explanation": "x",
        }
        base.update(overrides)
        return base

    def test_invalid_evidence_quality_becomes_insufficient(self, monkeypatch):
        out = self._run(monkeypatch, self._base(evidence_quality="excellent"))
        assert out["evidence_quality"] == "insufficient"

    def test_evidence_quality_case_insensitive(self, monkeypatch):
        out = self._run(monkeypatch, self._base(evidence_quality="STRONG"))
        assert out["evidence_quality"] == "strong"

    def test_all_valid_evidence_quality_values(self, monkeypatch):
        for value in ("strong", "weak", "insufficient", "misleading"):
            out = self._run(monkeypatch, self._base(evidence_quality=value))
            assert out["evidence_quality"] == value

    def test_consistency_score_clamped_above_one(self, monkeypatch):
        out = self._run(monkeypatch, self._base(consistency_score=1.5))
        assert out["consistency_score"] == 1.0

    def test_risk_contribution_clamped_below_zero(self, monkeypatch):
        out = self._run(monkeypatch, self._base(risk_contribution=-0.5))
        assert out["risk_contribution"] == 0.0

    def test_non_numeric_consistency_score_uses_fallback(self, monkeypatch):
        out = self._run(monkeypatch, self._base(consistency_score="n/a"))
        assert out["consistency_score"] == 0.4

    def test_empty_explanation_uses_fallback(self, monkeypatch):
        out = self._run(monkeypatch, self._base(explanation=""))
        assert out["explanation"] == "Could not fully cross-check the claims in this content."


# ─── boolean coercion ────────────────────────────────────────────────────────

class TestBooleanCoercion:
    def _run(self, monkeypatch, claim_supported, conflicting, date_ok) -> dict:
        _patch(monkeypatch, json.dumps({
            "claim_supported": claim_supported,
            "conflicting_sources": conflicting,
            "date_context_ok": date_ok,
            "evidence_quality": "insufficient",
            "consistency_score": 0.4,
            "risk_contribution": 0.6,
            "explanation": "test",
        }))
        return cc.cross_check_claims("sample")

    def test_json_booleans(self, monkeypatch):
        out = self._run(monkeypatch, True, False, True)
        assert out["claim_supported"] is True
        assert out["conflicting_sources"] is False
        assert out["date_context_ok"] is True

    def test_string_false_not_truthy(self, monkeypatch):
        out = self._run(monkeypatch, "false", "false", "false")
        assert out["claim_supported"] is False
        assert out["conflicting_sources"] is False
        assert out["date_context_ok"] is False

    def test_string_true_coerced(self, monkeypatch):
        out = self._run(monkeypatch, "true", "yes", "1")
        assert out["claim_supported"] is True
        assert out["conflicting_sources"] is True
        assert out["date_context_ok"] is True

    def test_none_uses_default_fallback(self, monkeypatch):
        out = self._run(monkeypatch, None, None, None)
        # defaults: claim_supported=False, conflicting_sources=False, date_context_ok=True
        assert out["claim_supported"] is False
        assert out["conflicting_sources"] is False
        assert out["date_context_ok"] is True
