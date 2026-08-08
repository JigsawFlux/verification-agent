# src/scoring.py
import os
import logging
from pathlib import Path
from typing import List

import yaml

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent.parent / "configs" / "thresholds.yaml"


def _load_config() -> dict:
    with open(_CONFIG_PATH) as f:
        return yaml.safe_load(f)


def compute_risk_score(evidence: List[dict]) -> tuple[float, float]:
    """
    Combine tool evidence into (risk_score, confidence).

    risk_score: 0.0–1.0  (higher = more risky)
    confidence: 0.0–1.0  (higher = more certain about the score)
    """
    cfg = _load_config()
    weights = cfg["weights"]
    multipliers = cfg["high_harm_multipliers"]

    tool_weight_map = {
        "check_source_credibility": weights["source_credibility"],
        "detect_manipulation_language": weights["manipulation_language"],
        "cross_check_claims": weights["cross_check"],
        "privacy_risk_check": weights["privacy_risk"],
    }

    weighted_sum = 0.0
    total_weight = 0.0
    error_count = 0

    for item in evidence:
        tool = item.get("tool", "")
        if "error" in item:
            error_count += 1
            continue
        weight = tool_weight_map.get(tool, 0.0)
        if weight == 0.0:
            continue

        base_risk = float(item.get("risk_contribution", 0.5))

        # Apply high-harm multipliers
        boost = 1.0
        if item.get("impersonation"):
            boost = max(boost, multipliers.get("impersonation", 1.5))
        if item.get("payment_pressure"):
            boost = max(boost, multipliers.get("payment_pressure", 1.5))
        if item.get("credential_harvesting"):
            boost = max(boost, multipliers.get("credential_harvesting", 1.8))
        if item.get("pii_solicitation"):
            boost = max(boost, multipliers.get("pii_solicitation", 1.4))

        adjusted_risk = min(base_risk * boost, 1.0)
        weighted_sum += adjusted_risk * weight
        total_weight += weight

    if total_weight == 0.0:
        return 0.5, 0.0

    risk_score = weighted_sum / total_weight
    # Confidence drops for every errored tool (each error = 25% penalty)
    confidence = max(0.0, 1.0 - (error_count * 0.25))
    return round(min(risk_score, 1.0), 4), round(confidence, 4)


def score_to_band(risk_score: float, confidence: float) -> str:
    """
    Map risk_score → Low/Medium/High, subject to confidence rules:
    - confidence < confidence_floor_for_low_risk → cannot output 'Low'
    - confidence < escalation_confidence_threshold → 'High' (force escalation signal)
    """
    cfg = _load_config()
    bands = cfg["bands"]
    confidence_floor = cfg.get("confidence_floor_for_low_risk", 0.60)
    escalation_threshold = cfg.get("escalation_confidence_threshold", 0.40)

    if confidence < escalation_threshold:
        return "High"

    low_min, low_max = bands["low"]
    medium_min, medium_max = bands["medium"]

    if low_min <= risk_score < low_max:
        if confidence < confidence_floor:
            return "Medium"
        return "Low"
    if medium_min <= risk_score < medium_max:
        return "Medium"
    return "High"


def should_escalate(confidence: float, risk_level: str, evidence: List[dict]) -> bool:
    """Escalate to human review if confidence is low or any high-harm signal fired."""
    cfg = _load_config()
    threshold = cfg.get("escalation_confidence_threshold", 0.40)
    if confidence < threshold:
        return True
    for item in evidence:
        if item.get("impersonation") or item.get("credential_harvesting"):
            return True
    return False
