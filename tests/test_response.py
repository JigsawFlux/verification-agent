# tests/test_response.py
import pytest
from src.formatter import format_response, render_cli


def _make_response(**overrides) -> dict:
    base = dict(
        risk_level="Medium",
        reasons=["No author identified.", "Urgency language present.", "Claims unverified."],
        next_step="Check the claim on an official website.",
        phase_log=["plan: done", "execute: done", "adapt: done", "follow_up: done"],
        escalate=False,
        confidence=0.75,
    )
    base.update(overrides)
    return format_response(**base)


class TestResponseContract:
    def test_all_four_blocks_present(self):
        resp = _make_response()
        assert "trust_summary" in resp
        assert "risk_level" in resp
        assert "reasons" in resp
        assert "next_step" in resp

    def test_reasons_never_empty(self):
        resp = _make_response(reasons=[])
        assert len(resp["reasons"]) >= 1

    def test_reasons_capped_at_three(self):
        resp = _make_response(reasons=["a", "b", "c", "d", "e"])
        assert len(resp["reasons"]) <= 3

    def test_escalation_flag_propagates(self):
        resp = _make_response(escalate=True)
        assert resp["escalate"] is True
        assert resp["needs_human_verification"] is True

    def test_low_risk_trust_summary_content(self):
        resp = _make_response(risk_level="Low", escalate=False)
        assert "reliable" in resp["trust_summary"].lower()

    def test_high_risk_trust_summary_content(self):
        resp = _make_response(risk_level="High", escalate=False)
        assert "serious" in resp["trust_summary"].lower() or "concern" in resp["trust_summary"].lower()

    def test_escalation_trust_summary_content(self):
        resp = _make_response(risk_level="High", escalate=True)
        assert "human verification" in resp["trust_summary"].lower()

    def test_risk_icon_present(self):
        resp = _make_response(risk_level="High")
        assert resp["risk_icon"] == "🔴"


class TestCliRender:
    def test_render_contains_risk_level(self):
        resp = _make_response(risk_level="High")
        rendered = render_cli(resp)
        assert "High" in rendered

    def test_render_contains_next_step(self):
        resp = _make_response()
        rendered = render_cli(resp)
        assert "Next Step" in rendered

    def test_render_shows_human_verification_on_escalate(self):
        resp = _make_response(escalate=True)
        rendered = render_cli(resp)
        assert "HUMAN VERIFICATION" in rendered

    def test_render_no_horizontal_overflow_hint(self):
        resp = _make_response()
        rendered = render_cli(resp)
        for line in rendered.split("\n"):
            assert len(line) <= 80, f"Line too long: {line!r}"
