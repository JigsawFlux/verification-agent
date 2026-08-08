# tests/test_scoring.py
import pytest
from src.scoring import compute_risk_score, score_to_band, should_escalate


def _evidence(tool, risk_contribution, **extras) -> dict:
    return {"tool": tool, "risk_contribution": risk_contribution, **extras}


class TestComputeRiskScore:
    def test_all_low_risk(self):
        evidence = [
            _evidence("check_source_credibility", 0.1),
            _evidence("detect_manipulation_language", 0.1),
            _evidence("cross_check_claims", 0.1),
            _evidence("privacy_risk_check", 0.1),
        ]
        score, confidence = compute_risk_score(evidence)
        assert score < 0.35
        assert confidence == 1.0

    def test_all_high_risk(self):
        evidence = [
            _evidence("check_source_credibility", 0.9),
            _evidence("detect_manipulation_language", 0.9),
            _evidence("cross_check_claims", 0.9),
            _evidence("privacy_risk_check", 0.9),
        ]
        score, confidence = compute_risk_score(evidence)
        assert score >= 0.65

    def test_error_tools_reduce_confidence(self):
        evidence = [
            _evidence("check_source_credibility", 0.5),
            {"tool": "detect_manipulation_language", "error": "failed"},
            {"tool": "cross_check_claims", "error": "failed"},
            _evidence("privacy_risk_check", 0.5),
        ]
        _, confidence = compute_risk_score(evidence)
        assert confidence < 0.6

    def test_payment_pressure_multiplier_raises_score(self):
        evidence_no_multiplier = [
            _evidence("privacy_risk_check", 0.4),
            _evidence("check_source_credibility", 0.1),
            _evidence("detect_manipulation_language", 0.1),
            _evidence("cross_check_claims", 0.1),
        ]
        evidence_with_multiplier = [
            _evidence("privacy_risk_check", 0.4, payment_pressure=True),
            _evidence("check_source_credibility", 0.1),
            _evidence("detect_manipulation_language", 0.1),
            _evidence("cross_check_claims", 0.1),
        ]
        score_base, _ = compute_risk_score(evidence_no_multiplier)
        score_boosted, _ = compute_risk_score(evidence_with_multiplier)
        assert score_boosted > score_base

    def test_empty_evidence_returns_neutral(self):
        score, confidence = compute_risk_score([])
        assert score == 0.5
        assert confidence == 0.0


class TestScoreToBand:
    def test_low_band(self):
        assert score_to_band(0.2, 0.9) == "Low"

    def test_medium_band(self):
        assert score_to_band(0.5, 0.9) == "Medium"

    def test_high_band(self):
        assert score_to_band(0.8, 0.9) == "High"

    def test_low_confidence_prevents_low_band(self):
        # Score qualifies as Low, but confidence too low → Medium
        assert score_to_band(0.2, 0.4) == "Medium"

    def test_very_low_confidence_forces_high(self):
        # confidence below escalation threshold → High
        assert score_to_band(0.2, 0.2) == "High"


class TestShouldEscalate:
    def test_low_confidence_triggers_escalation(self):
        assert should_escalate(0.3, "High", []) is True

    def test_credential_harvesting_triggers_escalation(self):
        evidence = [{"credential_harvesting": True}]
        assert should_escalate(0.9, "High", evidence) is True

    def test_normal_case_no_escalation(self):
        assert should_escalate(0.8, "High", []) is False
