# src/tools/privacy_risk.py
import json
import logging
from langchain_core.messages import SystemMessage, HumanMessage
from shared.llm import get_llm
from src.tools.adapter import register
from src.tools._shared import _extract_json, _as_bool, _clamp01

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are a privacy and safety analyst. Assess whether the provided content attempts to "
    "harvest personal information, payment details, or credentials. "
    "Return a JSON object with exactly these fields:\n"
    "  pii_solicitation (bool): does the content ask for personal identifiers (NI number, passport, etc.)?\n"
    "  payment_pressure (bool): does it request payment or financial information?\n"
    "  credential_harvesting (bool): does it request passwords, PINs, or account credentials?\n"
    "  impersonation (bool): does it impersonate a government body, bank, or well-known organisation?\n"
    "  safety_warning_text (str): a 1-sentence plain-English warning for the user (empty string if no risk)\n"
    "  risk_contribution (float 0.0-1.0): overall privacy/safety risk (1=high risk)\n"
    "  explanation (str): one plain-English sentence summarising the privacy risk assessment\n"
    "Return ONLY valid JSON. No markdown, no explanation outside the JSON."
)


def _default_result() -> dict:
    return {
        "pii_solicitation": False,
        "payment_pressure": False,
        "credential_harvesting": False,
        "impersonation": False,
        "safety_warning_text": "",
        "risk_contribution": 0.4,
        "explanation": "Could not fully assess privacy and safety risks.",
    }


def _sanitize(payload: dict) -> dict:
    result = _default_result()
    result["pii_solicitation"] = _as_bool(
        payload.get("pii_solicitation"), result["pii_solicitation"]
    )
    result["payment_pressure"] = _as_bool(
        payload.get("payment_pressure"), result["payment_pressure"]
    )
    result["credential_harvesting"] = _as_bool(
        payload.get("credential_harvesting"), result["credential_harvesting"]
    )
    result["impersonation"] = _as_bool(payload.get("impersonation"), result["impersonation"])

    warning = str(payload.get("safety_warning_text", result["safety_warning_text"])).strip()
    result["safety_warning_text"] = warning

    result["risk_contribution"] = _clamp01(
        payload.get("risk_contribution"), result["risk_contribution"]
    )

    explanation = str(payload.get("explanation", result["explanation"])).strip()
    result["explanation"] = explanation if explanation else result["explanation"]

    return result


@register("privacy_risk_check")
def privacy_risk_check(content: str) -> dict:
    """
    Input schema:  content (str)
    Output schema: pii_solicitation, payment_pressure, credential_harvesting,
                   impersonation, safety_warning_text, risk_contribution, explanation
    """
    llm = get_llm(temperature=0.0)
    prompt = f"Content to assess for privacy/safety risks:\n\n{content[:3000]}"
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
        logger.warning("privacy_risk: JSON parse/validation failed, returning defaults")
        return _default_result()
