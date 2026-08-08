# tests/test_manipulation_language.py
import json
import src.tools.manipulation_language as ml
from tests.conftest import FakeLLM


def _patch(monkeypatch, content: str):
    monkeypatch.setattr(ml, "get_llm", lambda temperature=0.0: FakeLLM(content))


# ─── JSON extraction ─────────────────────────────────────────────────────────

class TestJsonExtraction:
    def test_parses_plain_json(self, monkeypatch):
        payload = json.dumps({
            "urgency_present": True,
            "fear_language": False,
            "authority_pressure": False,
            "evidence_snippets": ["Act now!"],
            "risk_contribution": 0.7,
            "explanation": "Contains urgency language.",
        })
        _patch(monkeypatch, payload)
        out = ml.detect_manipulation_language("sample")
        assert out["urgency_present"] is True
        assert out["risk_contribution"] == 0.7

    def test_parses_fenced_json(self, monkeypatch):
        body = json.dumps({
            "urgency_present": False, "fear_language": True,
            "authority_pressure": False, "evidence_snippets": [],
            "risk_contribution": 0.6, "explanation": "Fear language detected.",
        })
        _patch(monkeypatch, f"```json\n{body}\n```")
        out = ml.detect_manipulation_language("sample")
        assert out["fear_language"] is True

    def test_parses_json_embedded_in_prose(self, monkeypatch):
        inner = json.dumps({
            "urgency_present": False, "fear_language": False,
            "authority_pressure": True, "evidence_snippets": [],
            "risk_contribution": 0.5, "explanation": "Authority claimed.",
        })
        _patch(monkeypatch, f"My analysis: {inner}")
        out = ml.detect_manipulation_language("sample")
        assert out["authority_pressure"] is True

    def test_extracts_first_object_when_multiple_fragments_in_prose(self, monkeypatch):
        first = json.dumps({
            "urgency_present": True, "fear_language": False,
            "authority_pressure": False, "evidence_snippets": ["hurry"],
            "risk_contribution": 0.8, "explanation": "First.",
        })
        second = json.dumps({
            "urgency_present": False, "fear_language": True,
            "authority_pressure": False, "evidence_snippets": [],
            "risk_contribution": 0.3, "explanation": "Second.",
        })
        _patch(monkeypatch, f"Option A: {first} Option B: {second}")
        out = ml.detect_manipulation_language("sample")
        assert out["explanation"] == "First."

    def test_returns_defaults_on_invalid_json(self, monkeypatch):
        _patch(monkeypatch, "not-json at all")
        out = ml.detect_manipulation_language("sample")
        assert out["urgency_present"] is False
        assert out["risk_contribution"] == 0.5

    def test_returns_defaults_when_response_is_json_array(self, monkeypatch):
        _patch(monkeypatch, '[{"urgency_present": true}]')
        out = ml.detect_manipulation_language("sample")
        assert out["urgency_present"] is False


# ─── _sanitize edge cases ────────────────────────────────────────────────────

class TestSanitize:
    def _run(self, monkeypatch, payload: dict) -> dict:
        _patch(monkeypatch, json.dumps(payload))
        return ml.detect_manipulation_language("sample")

    def _base(self, **overrides) -> dict:
        base = {
            "urgency_present": False, "fear_language": False,
            "authority_pressure": False, "evidence_snippets": [],
            "risk_contribution": 0.5, "explanation": "x",
        }
        base.update(overrides)
        return base

    def test_risk_contribution_clamped_above_one(self, monkeypatch):
        out = self._run(monkeypatch, self._base(risk_contribution=2.5))
        assert out["risk_contribution"] == 1.0

    def test_risk_contribution_clamped_below_zero(self, monkeypatch):
        out = self._run(monkeypatch, self._base(risk_contribution=-0.1))
        assert out["risk_contribution"] == 0.0

    def test_non_numeric_risk_contribution_uses_fallback(self, monkeypatch):
        out = self._run(monkeypatch, self._base(risk_contribution="high"))
        assert out["risk_contribution"] == 0.5

    def test_empty_explanation_uses_fallback(self, monkeypatch):
        out = self._run(monkeypatch, self._base(explanation=""))
        assert out["explanation"] == "Could not fully assess manipulation language."

    def test_evidence_snippets_capped_at_three(self, monkeypatch):
        out = self._run(monkeypatch, self._base(evidence_snippets=["a", "b", "c", "d", "e"]))
        assert len(out["evidence_snippets"]) == 3

    def test_evidence_snippets_non_list_becomes_empty(self, monkeypatch):
        out = self._run(monkeypatch, self._base(evidence_snippets="not a list"))
        assert out["evidence_snippets"] == []

    def test_evidence_snippets_items_coerced_to_str(self, monkeypatch):
        out = self._run(monkeypatch, self._base(evidence_snippets=[1, 2]))
        assert out["evidence_snippets"] == ["1", "2"]


# ─── boolean coercion ────────────────────────────────────────────────────────

class TestBooleanCoercion:
    def _run(self, monkeypatch, urgency, fear, authority) -> dict:
        _patch(monkeypatch, json.dumps({
            "urgency_present": urgency, "fear_language": fear,
            "authority_pressure": authority, "evidence_snippets": [],
            "risk_contribution": 0.5, "explanation": "test",
        }))
        return ml.detect_manipulation_language("sample")

    def test_json_booleans(self, monkeypatch):
        out = self._run(monkeypatch, True, False, True)
        assert out["urgency_present"] is True
        assert out["fear_language"] is False
        assert out["authority_pressure"] is True

    def test_string_false_not_truthy(self, monkeypatch):
        out = self._run(monkeypatch, "false", "false", "false")
        assert out["urgency_present"] is False
        assert out["fear_language"] is False
        assert out["authority_pressure"] is False

    def test_string_true_coerced(self, monkeypatch):
        out = self._run(monkeypatch, "true", "yes", "1")
        assert out["urgency_present"] is True
        assert out["fear_language"] is True
        assert out["authority_pressure"] is True

    def test_none_uses_fallback(self, monkeypatch):
        out = self._run(monkeypatch, None, None, None)
        assert out["urgency_present"] is False
        assert out["fear_language"] is False
        assert out["authority_pressure"] is False
