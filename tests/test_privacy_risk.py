# tests/test_privacy_risk.py
import json
import src.tools.privacy_risk as pr
from tests.conftest import FakeLLM


def _patch(monkeypatch, content: str):
    monkeypatch.setattr(pr, "get_llm", lambda temperature=0.0: FakeLLM(content))


# ─── JSON extraction ─────────────────────────────────────────────────────────

class TestJsonExtraction:
    def test_parses_plain_json(self, monkeypatch):
        payload = json.dumps({
            "pii_solicitation": True, "payment_pressure": False,
            "credential_harvesting": False, "impersonation": False,
            "safety_warning_text": "Do not share your NI number.",
            "risk_contribution": 0.8, "explanation": "PII requested.",
        })
        _patch(monkeypatch, payload)
        out = pr.privacy_risk_check("sample")
        assert out["pii_solicitation"] is True
        assert out["risk_contribution"] == 0.8

    def test_parses_fenced_json(self, monkeypatch):
        body = json.dumps({
            "pii_solicitation": False, "payment_pressure": True,
            "credential_harvesting": False, "impersonation": True,
            "safety_warning_text": "Possible bank impersonation.",
            "risk_contribution": 0.9, "explanation": "Payment and impersonation.",
        })
        _patch(monkeypatch, f"```json\n{body}\n```")
        out = pr.privacy_risk_check("sample")
        assert out["impersonation"] is True
        assert out["risk_contribution"] == 0.9

    def test_parses_json_embedded_in_prose(self, monkeypatch):
        inner = json.dumps({
            "pii_solicitation": False, "payment_pressure": False,
            "credential_harvesting": True, "impersonation": False,
            "safety_warning_text": "Password harvesting detected.",
            "risk_contribution": 0.95, "explanation": "Credential harvesting.",
        })
        _patch(monkeypatch, f"My assessment: {inner}")
        out = pr.privacy_risk_check("sample")
        assert out["credential_harvesting"] is True

    def test_extracts_first_object_when_multiple_fragments_in_prose(self, monkeypatch):
        first = json.dumps({
            "pii_solicitation": True, "payment_pressure": False,
            "credential_harvesting": False, "impersonation": False,
            "safety_warning_text": "", "risk_contribution": 0.7,
            "explanation": "First.",
        })
        second = json.dumps({
            "pii_solicitation": False, "payment_pressure": True,
            "credential_harvesting": False, "impersonation": False,
            "safety_warning_text": "", "risk_contribution": 0.3,
            "explanation": "Second.",
        })
        _patch(monkeypatch, f"Option A: {first} Option B: {second}")
        out = pr.privacy_risk_check("sample")
        assert out["explanation"] == "First."

    def test_returns_defaults_on_invalid_json(self, monkeypatch):
        _patch(monkeypatch, "not-json at all")
        out = pr.privacy_risk_check("sample")
        assert out["pii_solicitation"] is False
        assert out["risk_contribution"] == 0.4

    def test_returns_defaults_when_response_is_json_array(self, monkeypatch):
        _patch(monkeypatch, '[{"pii_solicitation": true}]')
        out = pr.privacy_risk_check("sample")
        assert out["pii_solicitation"] is False


# ─── _sanitize edge cases ────────────────────────────────────────────────────

class TestSanitize:
    def _run(self, monkeypatch, payload: dict) -> dict:
        _patch(monkeypatch, json.dumps(payload))
        return pr.privacy_risk_check("sample")

    def _base(self, **overrides) -> dict:
        base = {
            "pii_solicitation": False, "payment_pressure": False,
            "credential_harvesting": False, "impersonation": False,
            "safety_warning_text": "", "risk_contribution": 0.4,
            "explanation": "x",
        }
        base.update(overrides)
        return base

    def test_risk_contribution_clamped_above_one(self, monkeypatch):
        out = self._run(monkeypatch, self._base(risk_contribution=1.5))
        assert out["risk_contribution"] == 1.0

    def test_risk_contribution_clamped_below_zero(self, monkeypatch):
        out = self._run(monkeypatch, self._base(risk_contribution=-0.2))
        assert out["risk_contribution"] == 0.0

    def test_non_numeric_risk_contribution_uses_fallback(self, monkeypatch):
        out = self._run(monkeypatch, self._base(risk_contribution="critical"))
        assert out["risk_contribution"] == 0.4

    def test_empty_explanation_uses_fallback(self, monkeypatch):
        out = self._run(monkeypatch, self._base(explanation=""))
        assert out["explanation"] == "Could not fully assess privacy and safety risks."

    def test_safety_warning_text_passed_through(self, monkeypatch):
        out = self._run(monkeypatch, self._base(safety_warning_text="Never share your password."))
        assert out["safety_warning_text"] == "Never share your password."

    def test_safety_warning_text_coerced_to_str(self, monkeypatch):
        out = self._run(monkeypatch, self._base(safety_warning_text=None))
        assert isinstance(out["safety_warning_text"], str)

    def test_missing_fields_use_defaults(self, monkeypatch):
        _patch(monkeypatch, "{}")
        out = pr.privacy_risk_check("sample")
        assert out["pii_solicitation"] is False
        assert out["risk_contribution"] == 0.4
        assert out["explanation"] == "Could not fully assess privacy and safety risks."


# ─── boolean coercion ────────────────────────────────────────────────────────

class TestBooleanCoercion:
    def _run(self, monkeypatch, pii, payment, credential, impersonation) -> dict:
        _patch(monkeypatch, json.dumps({
            "pii_solicitation": pii, "payment_pressure": payment,
            "credential_harvesting": credential, "impersonation": impersonation,
            "safety_warning_text": "", "risk_contribution": 0.4, "explanation": "test",
        }))
        return pr.privacy_risk_check("sample")

    def test_json_booleans(self, monkeypatch):
        out = self._run(monkeypatch, True, True, False, False)
        assert out["pii_solicitation"] is True
        assert out["payment_pressure"] is True
        assert out["credential_harvesting"] is False
        assert out["impersonation"] is False

    def test_string_false_not_truthy(self, monkeypatch):
        out = self._run(monkeypatch, "false", "false", "false", "false")
        assert out["pii_solicitation"] is False
        assert out["payment_pressure"] is False
        assert out["credential_harvesting"] is False
        assert out["impersonation"] is False

    def test_string_true_variants(self, monkeypatch):
        out = self._run(monkeypatch, "true", "yes", "1", "True")
        assert out["pii_solicitation"] is True
        assert out["payment_pressure"] is True
        assert out["credential_harvesting"] is True
        assert out["impersonation"] is True

    def test_none_uses_fallback(self, monkeypatch):
        out = self._run(monkeypatch, None, None, None, None)
        assert out["pii_solicitation"] is False
        assert out["payment_pressure"] is False
        assert out["credential_harvesting"] is False
        assert out["impersonation"] is False
