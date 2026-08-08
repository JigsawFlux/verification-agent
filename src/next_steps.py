# src/next_steps.py
from pathlib import Path
from typing import List

import yaml

_CONFIG_PATH = Path(__file__).parent.parent / "configs" / "next_steps.yaml"


def _load_config() -> dict:
    with open(_CONFIG_PATH) as f:
        return yaml.safe_load(f)


def get_next_step(risk_level: str, evidence: List[dict], escalate: bool, input_type: str) -> str:
    """
    Return a safe, plain-English next-step for the user.
    Selects the most specific guidance available from the next_steps config.
    """
    cfg = _load_config()

    if escalate:
        return cfg["escalate"]["default"]

    band = risk_level.lower()
    band_cfg = cfg.get(band, {})

    if not band_cfg:
        return cfg["high"]["default"]

    # High-risk: look for the most specific high-harm next step
    if band == "high":
        for item in evidence:
            if item.get("credential_harvesting") or item.get("pii_solicitation"):
                return band_cfg.get("credential", band_cfg["default"])
            if item.get("payment_pressure"):
                return band_cfg.get("payment_pressure", band_cfg["default"])
            if item.get("impersonation"):
                return band_cfg.get("impersonation", band_cfg["default"])
        return band_cfg.get("scam", band_cfg["default"])

    # Medium-risk: try to pick most relevant variant
    if band == "medium":
        for item in evidence:
            if item.get("tool") == "detect_manipulation_language" and (
                item.get("urgency_present") or item.get("fear_language")
            ):
                return band_cfg.get("emotional_language", band_cfg["default"])
        for item in evidence:
            if item.get("tool") == "check_source_credibility" and not item.get("author_identifiable"):
                return band_cfg.get("missing_source", band_cfg["default"])
        return band_cfg["default"]

    # Low-risk
    if input_type == "url":
        return band_cfg.get("url", band_cfg["default"])
    return band_cfg["default"]
