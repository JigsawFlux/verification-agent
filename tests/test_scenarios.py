# tests/test_scenarios.py
"""
Seeded scenario tests — 5 representative inputs → expected risk bands.
These tests mock all LLM calls so they run offline and deterministically.
"""
import pytest
from unittest.mock import patch, MagicMock

from src.scoring import compute_risk_score, score_to_band


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _evidence_set(
    source_risk: float,
    manip_risk: float,
    cross_risk: float,
    privacy_risk: float,
    **kwargs
) -> list:
    return [
        {
            "tool": "check_source_credibility",
            "risk_contribution": source_risk,
            "source_known": source_risk < 0.4,
            "author_identifiable": source_risk < 0.4,
        },
        {
            "tool": "detect_manipulation_language",
            "risk_contribution": manip_risk,
            "urgency_present": manip_risk > 0.6,
            "fear_language": manip_risk > 0.7,
        },
        {
            "tool": "cross_check_claims",
            "risk_contribution": cross_risk,
            "claim_supported": cross_risk < 0.5,
        },
        {
            "tool": "privacy_risk_check",
            "risk_contribution": privacy_risk,
            "pii_solicitation": kwargs.get("pii_solicitation", False),
            "payment_pressure": kwargs.get("payment_pressure", False),
            "credential_harvesting": kwargs.get("credential_harvesting", False),
            "impersonation": kwargs.get("impersonation", False),
        },
    ]


# ─────────────────────────────────────────────
# Scenario 1: Obvious scam
# ─────────────────────────────────────────────
class TestObviousScam:
    """
    Input: "URGENT: Your account has been suspended. Click now to verify or lose access."
    Expected: High
    Signals: urgency + fear + payment pressure + no source
    """
    def test_risk_band_is_high(self):
        evidence = _evidence_set(
            source_risk=0.9,
            manip_risk=0.95,
            cross_risk=0.8,
            privacy_risk=0.85,
            payment_pressure=True,
        )
        score, confidence = compute_risk_score(evidence)
        band = score_to_band(score, confidence)
        assert band == "High", f"Expected High, got {band} (score={score}, confidence={confidence})"


# ─────────────────────────────────────────────
# Scenario 2: Credible source
# ─────────────────────────────────────────────
class TestCredibleSource:
    """
    Input: BBC News article text — established source, no urgency, claims supported
    Expected: Low
    """
    def test_risk_band_is_low(self):
        evidence = _evidence_set(
            source_risk=0.05,
            manip_risk=0.05,
            cross_risk=0.05,
            privacy_risk=0.05,
        )
        score, confidence = compute_risk_score(evidence)
        band = score_to_band(score, confidence)
        assert band == "Low", f"Expected Low, got {band} (score={score}, confidence={confidence})"


# ─────────────────────────────────────────────
# Scenario 3: Mixed signal — blog post with weak sourcing
# ─────────────────────────────────────────────
class TestMixedSignal:
    """
    Input: Blog post citing a single study with no named author.
    Expected: Medium
    Signals: unknown source + weak cross-check, but no manipulation or privacy risk
    """
    def test_risk_band_is_medium(self):
        evidence = _evidence_set(
            source_risk=0.6,
            manip_risk=0.2,
            cross_risk=0.55,
            privacy_risk=0.1,
        )
        score, confidence = compute_risk_score(evidence)
        band = score_to_band(score, confidence)
        assert band == "Medium", f"Expected Medium, got {band} (score={score}, confidence={confidence})"


# ─────────────────────────────────────────────
# Scenario 4: Missing source — unsupported health claim
# ─────────────────────────────────────────────
class TestMissingSource:
    """
    Input: "Scientists say chocolate cures cancer — share now!"
    Expected: Medium or High
    Signals: no source, unsupported claim, mild urgency
    """
    def test_risk_band_is_medium_or_high(self):
        evidence = _evidence_set(
            source_risk=0.8,
            manip_risk=0.5,
            cross_risk=0.75,
            privacy_risk=0.05,
        )
        score, confidence = compute_risk_score(evidence)
        band = score_to_band(score, confidence)
        assert band in ("Medium", "High"), f"Expected Medium or High, got {band}"


# ─────────────────────────────────────────────
# Scenario 5: Privacy harvesting
# ─────────────────────────────────────────────
class TestPrivacyHarvesting:
    """
    Input: "Enter your National Insurance number to claim your HMRC tax refund."
    Expected: High
    Signals: PII solicitation + impersonation + credential harvesting
    """
    def test_risk_band_is_high(self):
        evidence = _evidence_set(
            source_risk=0.85,
            manip_risk=0.6,
            cross_risk=0.7,
            privacy_risk=0.95,
            pii_solicitation=True,
            credential_harvesting=True,
            impersonation=True,
        )
        score, confidence = compute_risk_score(evidence)
        band = score_to_band(score, confidence)
        assert band == "High", f"Expected High, got {band} (score={score}, confidence={confidence})"

    def test_credential_harvesting_triggers_escalation(self):
        from src.scoring import should_escalate
        evidence = [{"credential_harvesting": True}]
        assert should_escalate(0.9, "High", evidence) is True
