# src/formatter.py
import textwrap
from typing import List


_RISK_ICONS = {
    "Low": "🟢",
    "Medium": "🟡",
    "High": "🔴",
}


def build_trust_summary(risk_level: str, reasons: List[str], escalate: bool) -> str:
    """Generate a 1–2 sentence plain-English trust summary."""
    if escalate:
        return (
            "The evidence is unclear or conflicting. "
            "This content needs human verification before you act or share it."
        )
    if risk_level == "Low":
        return (
            "This content appears broadly reliable based on the checks performed. "
            "Always verify important facts with an official source."
        )
    if risk_level == "Medium":
        reason_hint = reasons[0] if reasons else "some concerns were identified"
        return (
            f"This content has some reliability concerns — {reason_hint.lower()}. "
            "Verify the key claims before acting or sharing."
        )
    # High
    reason_hint = reasons[0] if reasons else "significant warning signs were found"
    return (
        f"This content has serious reliability concerns — {reason_hint.lower()}. "
        "Do not share or act on it until manually verified."
    )


def format_response(
    risk_level: str,
    reasons: List[str],
    next_step: str,
    phase_log: List[str],
    escalate: bool,
    confidence: float,
) -> dict:
    """
    Enforce the 4-block response contract:
      1. Trust Summary
      2. Risk Level
      3. Top 3 Reasons
      4. Suggested Next Step

    Always returns all 4 blocks. Never emits fewer than 1 reason.
    """
    if not reasons:
        reasons = ["Insufficient evidence to determine reliability."]

    top_reasons = reasons[:3]
    trust_summary = build_trust_summary(risk_level, top_reasons, escalate)

    return {
        "trust_summary": trust_summary,
        "risk_level": risk_level,
        "risk_icon": _RISK_ICONS.get(risk_level, "⚪"),
        "reasons": top_reasons,
        "next_step": next_step,
        "escalate": escalate,
        "confidence": confidence,
        "phase_log": phase_log,
        "needs_human_verification": escalate,
    }


def render_cli(response: dict) -> str:
    """Render the 4-block response as a readable CLI string."""
    icon = response.get("risk_icon", "")
    _wrap = lambda s: textwrap.fill(s, width=74, initial_indent="  ", subsequent_indent="  ")

    lines = [
        "",
        "=" * 56,
        f"  VERIFICATION RESULT",
        "=" * 56,
        f"  Risk Level:    {icon} {response['risk_level']}",
        f"  Confidence:    {int(response['confidence'] * 100)}%",
        "",
        "  Trust Summary",
        "  " + "-" * 52,
        _wrap(response['trust_summary']),
        "",
        "  Why:",
    ]
    for i, reason in enumerate(response["reasons"], 1):
        lines.append(_wrap(f"{i}. {reason}"))
    lines += [
        "",
        "  Next Step",
        "  " + "-" * 52,
        _wrap(response['next_step']),
    ]
    if response.get("needs_human_verification"):
        lines += [
            "",
            "  ⚠️  NEEDS HUMAN VERIFICATION",
        ]
    lines += ["", "=" * 56, ""]
    return "\n".join(lines)
