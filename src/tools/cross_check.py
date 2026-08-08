# src/tools/cross_check.py
import json
import logging
from langchain_core.messages import SystemMessage, HumanMessage
from shared.llm import get_llm
from src.tools.adapter import register
from src.tools._shared import _extract_json, _as_bool, _clamp01

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are a fact-checking analyst. Using your knowledge, assess whether the key claims in the "
    "provided content are consistent with well-established, independently verifiable facts. "
    "Return a JSON object with exactly these fields:\n"
    "  claim_supported (bool): are the main claims broadly supported by credible evidence?\n"
    "  conflicting_sources (bool): do you know of reliable sources that contradict these claims?\n"
    "  date_context_ok (bool): are dates, timeframes, and context consistent and current?\n"
    "  evidence_quality (str): 'strong' | 'weak' | 'insufficient' | 'misleading'\n"
    "  consistency_score (float 0.0-1.0): overall claim consistency (1=fully consistent)\n"
    "  risk_contribution (float 0.0-1.0): risk from inaccurate/misleading claims (1=high risk)\n"
    "  explanation (str): one plain-English sentence summarising the cross-check result\n"
    "Return ONLY valid JSON. No markdown, no explanation outside the JSON.\n"
    "IMPORTANT: If the content is too vague to assess, set evidence_quality to 'insufficient' "
    "and risk_contribution to 0.6."
)

_ALLOWED_EVIDENCE_QUALITY = {"strong", "weak", "insufficient", "misleading"}


def _default_result() -> dict:
    return {
        "claim_supported": False,
        "conflicting_sources": False,
        "date_context_ok": True,
        "evidence_quality": "insufficient",
        "consistency_score": 0.4,
        "risk_contribution": 0.6,
        "explanation": "Could not fully cross-check the claims in this content.",
    }


def _sanitize(payload: dict) -> dict:
    result = _default_result()
    result["claim_supported"] = _as_bool(payload.get("claim_supported"), result["claim_supported"])
    result["conflicting_sources"] = _as_bool(
        payload.get("conflicting_sources"), result["conflicting_sources"]
    )
    result["date_context_ok"] = _as_bool(payload.get("date_context_ok"), result["date_context_ok"])

    eq = str(payload.get("evidence_quality", result["evidence_quality"])).strip().lower()
    result["evidence_quality"] = eq if eq in _ALLOWED_EVIDENCE_QUALITY else "insufficient"

    result["consistency_score"] = _clamp01(
        payload.get("consistency_score"), result["consistency_score"]
    )
    result["risk_contribution"] = _clamp01(
        payload.get("risk_contribution"), result["risk_contribution"]
    )

    explanation = str(payload.get("explanation", result["explanation"])).strip()
    result["explanation"] = explanation if explanation else result["explanation"]

    return result


@register("cross_check_claims")
def cross_check_claims(content: str) -> dict:
    """
    Input schema:  content (str)
    Output schema: claim_supported, conflicting_sources, date_context_ok,
                   evidence_quality, consistency_score, risk_contribution, explanation
    """
    llm = get_llm(temperature=0.0)
    prompt = f"Content to fact-check:\n\n{content[:3000]}"
    response = llm.invoke([
        SystemMessage(content=_SYSTEM),
        HumanMessage(content=prompt),
    ])

    raw = _extract_json(
        response.content if isinstance(response.content, str) else str(response.content)
    )
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("Model output is not a JSON object")
        return _sanitize(parsed)
    except Exception:
        logger.warning("cross_check: JSON parse/validation failed, returning defaults")
        return _default_result()
