# src/tools/source_credibility.py
import json
import logging
from langchain_core.messages import SystemMessage, HumanMessage
from shared.llm import get_llm
from src.tools.adapter import register
from src.tools._shared import _extract_json, _as_bool, _clamp01

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are a source-credibility analyst. Assess the provided content and return "
    "a JSON object with exactly these fields:\n"
    "  source_known (bool): is the publishing source or organisation identifiable?\n"
    "  author_identifiable (bool): is a named author present?\n"
    "  domain_age_signal (str): 'established' | 'unknown' | 'suspicious'\n"
    "  credibility_score (float 0.0-1.0): overall source credibility (1=fully credible)\n"
    "  risk_contribution (float 0.0-1.0): risk posed by poor credibility (1=high risk)\n"
    "  explanation (str): one plain-English sentence explaining the assessment\n"
    "Return ONLY valid JSON. No markdown, no explanation outside the JSON."
)

_ALLOWED_DOMAIN_AGE = {"established", "unknown", "suspicious"}


def _default_result() -> dict:
    return {
        "source_known": False,
        "author_identifiable": False,
        "domain_age_signal": "unknown",
        "credibility_score": 0.3,
        "risk_contribution": 0.7,
        "explanation": "Could not fully assess source credibility.",
    }


def _sanitize(payload: dict) -> dict:
    result = _default_result()

    result["source_known"] = _as_bool(payload.get("source_known"), result["source_known"])
    result["author_identifiable"] = _as_bool(
        payload.get("author_identifiable"), result["author_identifiable"]
    )

    domain_age = str(payload.get("domain_age_signal", result["domain_age_signal"])).strip().lower()
    result["domain_age_signal"] = domain_age if domain_age in _ALLOWED_DOMAIN_AGE else "unknown"

    result["credibility_score"] = _clamp01(
        payload.get("credibility_score"), result["credibility_score"]
    )
    result["risk_contribution"] = _clamp01(
        payload.get("risk_contribution"), result["risk_contribution"]
    )

    explanation = str(payload.get("explanation", result["explanation"])).strip()
    result["explanation"] = explanation if explanation else result["explanation"]

    return result


@register("check_source_credibility")
def check_source_credibility(content: str) -> dict:
    """
    Input schema:  content (str) — extracted text or raw message
    Output schema: source_known, author_identifiable, domain_age_signal,
                   credibility_score, risk_contribution, explanation
    """
    llm = get_llm(temperature=0.0)
    prompt = f"Content to assess:\n\n{content[:3000]}"
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
        logger.warning("source_credibility: JSON parse/validation failed, returning defaults")
        return _default_result()
