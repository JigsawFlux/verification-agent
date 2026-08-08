# src/state.py
from typing import List, Optional
from typing_extensions import TypedDict
from pydantic import BaseModel, field_validator


class VerificationState(TypedDict):
    input: str
    input_type: str            # "url" | "text"
    extracted_content: str
    evidence: List[dict]
    signals: dict
    risk_score: float          # 0.0–1.0
    risk_level: str            # "Low" | "Medium" | "High"
    reasons: List[str]         # top 3 plain-language reasons
    next_step: str
    confidence: float          # 0.0–1.0
    phase_log: List[str]
    escalate: bool
    retry_count: int           # tracks adapter→executor retries


class StateValidationError(Exception):
    pass


class VerificationStateValidator(BaseModel):
    input: str
    input_type: str
    extracted_content: str
    evidence: List[dict]
    signals: dict
    risk_score: float
    risk_level: str
    reasons: List[str]
    next_step: str
    confidence: float
    phase_log: List[str]
    escalate: bool
    retry_count: int = 0

    @field_validator("input_type")
    @classmethod
    def validate_input_type(cls, v: str) -> str:
        if v not in ("url", "text"):
            raise ValueError(f"input_type must be 'url' or 'text', got '{v}'")
        return v

    @field_validator("risk_level")
    @classmethod
    def validate_risk_level(cls, v: str) -> str:
        if v not in ("Low", "Medium", "High", ""):
            raise ValueError(f"risk_level must be Low/Medium/High, got '{v}'")
        return v

    @field_validator("risk_score", "confidence")
    @classmethod
    def validate_float_range(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"Score/confidence must be in [0.0, 1.0], got {v}")
        return v

    @field_validator("reasons")
    @classmethod
    def validate_reasons(cls, v: List[str]) -> List[str]:
        if len(v) > 3:
            return v[:3]
        return v


def validate_state(state: dict) -> VerificationStateValidator:
    """Validate a state dict; raises StateValidationError on failure."""
    try:
        return VerificationStateValidator(**state)
    except Exception as exc:
        raise StateValidationError(str(exc)) from exc


def initial_state(user_input: str) -> VerificationState:
    """Return a clean initial state for a new verification run."""
    return VerificationState(
        input=user_input,
        input_type="",
        extracted_content="",
        evidence=[],
        signals={},
        risk_score=0.0,
        risk_level="",
        reasons=[],
        next_step="",
        confidence=0.0,
        phase_log=[],
        escalate=False,
        retry_count=0,
    )


SAFE_FALLBACK_RESPONSE = {
    "risk_level": "High",
    "trust_summary": "Unable to complete verification due to an internal error. Treat this content with caution.",
    "reasons": [
        "Verification process encountered an unexpected error.",
        "Cannot confirm the reliability of this content.",
        "Manual review is recommended.",
    ],
    "next_step": "Do not act on this content until it has been manually verified by a trusted source.",
    "escalate": True,
}
