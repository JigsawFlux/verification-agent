# src/tools/manipulation_language.py
import json
import logging
from langchain_core.messages import SystemMessage, HumanMessage
from shared.llm import get_llm
from src.tools.adapter import register
from src.tools._shared import _extract_json, _as_bool, _clamp01

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are a manipulation-language analyst. Assess the provided content and return "
    "a JSON object with exactly these fields:\n"
    "  urgency_present (bool): does the content use urgency or time-pressure language?\n"
    "  fear_language (bool): does it use fear, threat, or alarm language?\n"
    "  authority_pressure (bool): does it impersonate authority or use fake endorsements?\n"
    "  evidence_snippets (list of str): up to 3 verbatim phrases that triggered flags (empty list if none)\n"
    "  risk_contribution (float 0.0-1.0): overall manipulation risk (1=high risk)\n"
    "  explanation (str): one plain-English sentence summarising findings\n"
    "Return ONLY valid JSON. No markdown, no explanation outside the JSON."
)


def _default_result() -> dict:
    return {
        "urgency_present": False,
        "fear_language": False,
        "authority_pressure": False,
        "evidence_snippets": [],
        "risk_contribution": 0.5,
        "explanation": "Could not fully assess manipulation language.",
    }


def _sanitize(payload: dict) -> dict:
    result = _default_result()
    result["urgency_present"] = _as_bool(payload.get("urgency_present"), result["urgency_present"])
    result["fear_language"] = _as_bool(payload.get("fear_language"), result["fear_language"])
    result["authority_pressure"] = _as_bool(
        payload.get("authority_pressure"), result["authority_pressure"]
    )

    snippets = payload.get("evidence_snippets", [])
    if isinstance(snippets, list):
        result["evidence_snippets"] = [str(s) for s in snippets[:3]]

    result["risk_contribution"] = _clamp01(
        payload.get("risk_contribution"), result["risk_contribution"]
    )

    explanation = str(payload.get("explanation", result["explanation"])).strip()
    result["explanation"] = explanation if explanation else result["explanation"]

    return result


@register("detect_manipulation_language")
def detect_manipulation_language(content: str) -> dict:
    """
    Input schema:  content (str)
    Output schema: urgency_present, fear_language, authority_pressure,
                   evidence_snippets, risk_contribution, explanation
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
        logger.warning("manipulation_language: JSON parse/validation failed, returning defaults")
        return _default_result()
