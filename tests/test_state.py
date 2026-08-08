# tests/test_state.py
import pytest
from src.state import (
    validate_state,
    StateValidationError,
    initial_state,
    SAFE_FALLBACK_RESPONSE,
)


def _valid_state(**overrides) -> dict:
    base = dict(
        input="test message",
        input_type="text",
        extracted_content="test message",
        evidence=[],
        signals={},
        risk_score=0.5,
        risk_level="Medium",
        reasons=["Reason one"],
        next_step="Check the source.",
        confidence=0.8,
        phase_log=["plan: done"],
        escalate=False,
        retry_count=0,
    )
    base.update(overrides)
    return base


class TestStateValidation:
    def test_valid_state_passes(self):
        validate_state(_valid_state())

    def test_invalid_input_type_raises(self):
        with pytest.raises(StateValidationError):
            validate_state(_valid_state(input_type="pdf"))

    def test_invalid_risk_level_raises(self):
        with pytest.raises(StateValidationError):
            validate_state(_valid_state(risk_level="Critical"))

    def test_risk_score_out_of_range_raises(self):
        with pytest.raises(StateValidationError):
            validate_state(_valid_state(risk_score=1.5))

    def test_confidence_out_of_range_raises(self):
        with pytest.raises(StateValidationError):
            validate_state(_valid_state(confidence=-0.1))

    def test_reasons_truncated_to_3(self):
        result = validate_state(_valid_state(reasons=["a", "b", "c", "d", "e"]))
        assert len(result.reasons) == 3

    def test_empty_risk_level_allowed(self):
        validate_state(_valid_state(risk_level=""))


class TestInitialState:
    def test_initial_state_fields(self):
        state = initial_state("hello world")
        assert state["input"] == "hello world"
        assert state["evidence"] == []
        assert state["risk_score"] == 0.0
        assert state["escalate"] is False
        assert state["retry_count"] == 0


class TestSafeFallback:
    def test_fallback_has_all_required_keys(self):
        for key in ("risk_level", "trust_summary", "reasons", "next_step", "escalate"):
            assert key in SAFE_FALLBACK_RESPONSE

    def test_fallback_risk_is_high(self):
        assert SAFE_FALLBACK_RESPONSE["risk_level"] == "High"

    def test_fallback_has_reasons(self):
        assert len(SAFE_FALLBACK_RESPONSE["reasons"]) >= 1
