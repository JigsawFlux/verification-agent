# src/formatter.py
import html as _html_lib
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


def render_html(response: dict) -> str:
    """Render the 4-block response as a self-contained HTML page."""
    risk = response.get("risk_level", "Unknown")
    confidence = int(response.get("confidence", 0) * 100)
    trust_summary = _html_lib.escape(response.get("trust_summary", ""))
    reasons = [_html_lib.escape(r) for r in response.get("reasons", [])]
    next_step = _html_lib.escape(response.get("next_step", ""))
    escalate = response.get("needs_human_verification", False)

    risk_lower = risk.lower()
    reasons_html = "\n".join(
        f'<li><span class="n">{i}</span>{r}</li>'
        for i, r in enumerate(reasons, 1)
    )
    escalation_html = (
        '<div class="escalation">⚠ Needs Human Verification — do not act or share until reviewed</div>'
        if escalate else ""
    )
    confidence_pct = confidence / 100

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Verification Result — {_html_lib.escape(risk)} Risk</title>
<style>
:root {{
  --bg:#F0F2F5; --surface:#FFFFFF; --border:#DDE1EA;
  --text:#1C2030; --muted:#5E6878; --accent:#1A56DB;
  --risk-low:#15803D; --risk-medium:#B45309; --risk-high:#B91C1C;
  --risk-low-bg:#F0FDF4; --risk-medium-bg:#FFFBEB; --risk-high-bg:#FFF1F2;
}}
@media(prefers-color-scheme:dark){{:root:not([data-theme="light"]){{
  --bg:#0D0F14; --surface:#171A23; --border:#2A2D3A;
  --text:#E4E7F0; --muted:#8890A8;
  --risk-low-bg:#052E16; --risk-medium-bg:#1C1500; --risk-high-bg:#1C0A0A;
}}}}
:root[data-theme="dark"]{{
  --bg:#0D0F14; --surface:#171A23; --border:#2A2D3A;
  --text:#E4E7F0; --muted:#8890A8;
  --risk-low-bg:#052E16; --risk-medium-bg:#1C1500; --risk-high-bg:#1C0A0A;
}}
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--text);font-family:-apple-system,'Segoe UI',sans-serif;
  min-height:100vh;display:flex;align-items:center;justify-content:center;padding:2rem 1rem}}
.card{{background:var(--surface);border:1px solid var(--border);max-width:600px;width:100%;
  border-left:5px solid var(--risk-{risk_lower});overflow:hidden}}
.risk-header{{background:var(--risk-{risk_lower}-bg);padding:1.25rem 1.5rem;
  display:flex;align-items:baseline;justify-content:space-between;gap:1rem}}
.risk-level{{font-size:1.4rem;font-weight:700;color:var(--risk-{risk_lower});letter-spacing:-.01em}}
.confidence{{font-family:ui-monospace,'Courier New',monospace;font-size:.8rem;color:var(--muted);
  font-variant-numeric:tabular-nums}}
.confidence-bar{{height:3px;background:var(--border);border-radius:0;margin-top:.35rem}}
.confidence-fill{{height:100%;background:var(--risk-{risk_lower});width:{confidence_pct * 100:.0f}%}}
.body{{padding:1.5rem}}
.summary{{font-family:Georgia,'Times New Roman',serif;font-size:1.05rem;line-height:1.65;
  color:var(--text);margin-bottom:1.5rem;text-wrap:balance}}
.label{{font-size:.65rem;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);
  margin-bottom:.6rem}}
.reasons{{list-style:none;display:flex;flex-direction:column;gap:.75rem;margin-bottom:1.5rem}}
.reasons li{{display:flex;gap:.75rem;font-size:.9rem;line-height:1.5;padding-left:.5rem;
  border-left:2px solid var(--border);color:var(--text)}}
.reasons li .n{{font-family:ui-monospace,'Courier New',monospace;font-size:.75rem;
  color:var(--muted);min-width:1.2rem;padding-top:.15rem;flex-shrink:0}}
.next-step{{background:var(--bg);border:1px solid var(--border);padding:1rem 1.25rem;
  font-size:.875rem;line-height:1.6;color:var(--text)}}
.next-step-label{{font-size:.65rem;text-transform:uppercase;letter-spacing:.1em;
  color:var(--accent);margin-bottom:.4rem}}
.escalation{{background:#7F1D1D;color:#FEE2E2;padding:1rem 1.5rem;font-size:.875rem;
  font-weight:600;text-align:center;letter-spacing:.01em}}
</style>
</head>
<body>
<div class="card">
  <div class="risk-header">
    <div>
      <div class="risk-level">{_html_lib.escape(risk)} Risk</div>
      <div class="confidence-bar"><div class="confidence-fill"></div></div>
    </div>
    <div class="confidence">{confidence}% confidence</div>
  </div>
  <div class="body">
    <p class="summary">{trust_summary}</p>
    <p class="label">Why</p>
    <ol class="reasons">{reasons_html}</ol>
    <div class="next-step">
      <div class="next-step-label">Next Step</div>
      {next_step}
    </div>
  </div>
  {escalation_html}
</div>
</body>
</html>"""
