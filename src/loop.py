# src/loop.py
import logging
import os
import uuid
from typing import List

from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END

from shared.llm import get_llm
from shared.telemetry import TelemetryCallback
from src.privacy import HistoryStorage, redact_pii
from src.state import VerificationState, StateValidationError, validate_state, SAFE_FALLBACK_RESPONSE
from src.tools.adapter import ToolRegistry
from src.scoring import compute_risk_score, score_to_band, should_escalate
from src.next_steps import get_next_step
from src.formatter import format_response

logger = logging.getLogger(__name__)

_MAX_RETRIES = int(os.environ.get("MAX_RETRY_ON_LOW_CONFIDENCE", "1"))

_ALL_TOOLS = [
    "check_source_credibility",
    "detect_manipulation_language",
    "cross_check_claims",
    "privacy_risk_check",
]


# ─────────────────────────────────────────────
# Node 1: Planner
# Decides which tools to run and logs the plan.
# ─────────────────────────────────────────────
def planner_node(state: VerificationState) -> dict:
    phase_log = list(state.get("phase_log", []))
    phase_log.append("plan: selected tools for verification run")
    logger.info("[plan] input_type=%s", state["input_type"])

    # For MVP: always run all 4 tools; future versions could narrow by input_type
    return {"phase_log": phase_log}


# ─────────────────────────────────────────────
# Node 2: Executor
# Runs all 4 tool checks and populates evidence + signals.
# ─────────────────────────────────────────────
def executor_node(state: VerificationState) -> dict:
    phase_log = list(state.get("phase_log", []))
    phase_log.append("execute: running verification tools")
    content = state["extracted_content"]

    evidence = []
    for tool_name in _ALL_TOOLS:
        logger.info("[execute] calling %s", tool_name)
        result = ToolRegistry.run(tool_name, content)
        evidence.append(result)

    # Collapse signals into a flat dict for easy downstream use
    signals = {}
    for item in evidence:
        tool = item.get("tool", "")
        for key, val in item.items():
            if key not in ("tool", "error", "explanation"):
                signals[f"{tool}.{key}"] = val

    return {"evidence": evidence, "signals": signals, "phase_log": phase_log}


# ─────────────────────────────────────────────
# Node 3: Adapter
# Handles conflicting or insufficient evidence.
# Adjusts confidence and decides if retry is needed.
# ─────────────────────────────────────────────
def adapter_node(state: VerificationState) -> dict:
    phase_log = list(state.get("phase_log", []))
    evidence = state["evidence"]
    retry_count = state.get("retry_count", 0)

    risk_score, confidence = compute_risk_score(evidence)

    # Detect conflicting evidence: one tool says low risk, another says high
    contributions = [
        e.get("risk_contribution", 0.5)
        for e in evidence
        if "error" not in e
    ]
    has_conflict = (
        len(contributions) >= 2
        and max(contributions) > 0.7
        and min(contributions) < 0.3
    )

    adapted = False
    if has_conflict:
        phase_log.append("adapt: conflicting evidence detected — adjusting confidence")
        confidence = max(0.0, confidence - 0.2)
        adapted = True
    else:
        phase_log.append("adapt: evidence consistent — no adjustment needed")

    # Decide whether to retry with a broadened prompt
    should_retry = (
        confidence < 0.4
        and retry_count < _MAX_RETRIES
        and not adapted  # don't retry after we already adapted
    )

    if should_retry:
        phase_log.append(f"adapt: low confidence ({confidence:.2f}) — scheduling retry")

    return {
        "risk_score": risk_score,
        "confidence": confidence,
        "phase_log": phase_log,
        "retry_count": retry_count + (1 if should_retry else 0),
    }


def should_retry_or_continue(state: VerificationState) -> str:
    """Route: retry executor if low-confidence and retries remain; else proceed to follow-up."""
    confidence = state.get("confidence", 1.0)
    retry_count = state.get("retry_count", 0)
    if confidence < 0.4 and retry_count <= _MAX_RETRIES:
        return "executor"
    return "followup"


# ─────────────────────────────────────────────
# Node 4: Follow-up
# Final scoring → risk band → reasons → next step → formatted output.
# ─────────────────────────────────────────────
def followup_node(state: VerificationState) -> dict:
    phase_log = list(state.get("phase_log", []))
    phase_log.append("follow_up: generating final verification report")

    evidence = state["evidence"]
    risk_score = state["risk_score"]
    confidence = state["confidence"]
    input_type = state["input_type"]

    risk_level = score_to_band(risk_score, confidence)
    escalate = should_escalate(confidence, risk_level, evidence)

    # Generate plain-English reasons from tool explanations + signal flags
    reasons = _build_reasons(evidence, risk_level)
    next_step = get_next_step(risk_level, evidence, escalate, input_type)

    return {
        "risk_level": risk_level,
        "reasons": reasons,
        "next_step": next_step,
        "escalate": escalate,
        "phase_log": phase_log,
    }


def _build_reasons(evidence: List[dict], risk_level: str) -> List[str]:
    """Extract up to 3 plain-language reason sentences from tool outputs."""
    reasons = []
    for item in evidence:
        if "error" in item:
            continue
        explanation = item.get("explanation", "")
        if explanation:
            reasons.append(explanation)

    # Supplement with specific signal-level reasons if needed
    if len(reasons) < 3:
        for item in evidence:
            if item.get("urgency_present") or item.get("fear_language"):
                reasons.append("The content uses urgency or fear-based language to pressure the reader.")
                break
        for item in evidence:
            if item.get("credential_harvesting") or item.get("pii_solicitation"):
                reasons.append("Personal credentials or identifiers are being requested.")
                break
        for item in evidence:
            if not item.get("source_known") and not item.get("author_identifiable"):
                reasons.append("No identifiable source or author was found.")
                break

    if not reasons:
        reasons = ["Insufficient evidence was available to make a confident assessment."]

    return reasons[:3]


# ─────────────────────────────────────────────
# Graph assembly
# ─────────────────────────────────────────────
def build_verification_graph():
    workflow = StateGraph(VerificationState)

    workflow.add_node("planner", planner_node)
    workflow.add_node("executor", executor_node)
    workflow.add_node("adapter", adapter_node)
    workflow.add_node("followup", followup_node)

    workflow.add_edge(START, "planner")
    workflow.add_edge("planner", "executor")
    workflow.add_edge("executor", "adapter")

    workflow.add_conditional_edges(
        "adapter",
        should_retry_or_continue,
        {"executor": "executor", "followup": "followup"},
    )
    workflow.add_edge("followup", END)

    return workflow.compile()


# ─────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────
def run_verification(user_input: str) -> dict:
    """
    Run the full verification pipeline for a user's input (URL or text).
    Returns a formatted response dict ready for CLI rendering.
    """
    from src.fetcher import prepare_content

    fetch_result = prepare_content(user_input)
    input_type = fetch_result.input_type

    if not fetch_result.success:
        logger.warning(
            "Content fetch failed: reason=%s url=%s",
            fetch_result.error_reason,
            fetch_result.url_sanitized,
        )
        content = f"[Content unavailable: {fetch_result.error_reason}] {fetch_result.url_sanitized}"
    else:
        content = fetch_result.content

    if not content.strip():
        return SAFE_FALLBACK_RESPONSE

    initial = {
        "input": user_input,
        "input_type": input_type,
        "extracted_content": content,
        "evidence": [],
        "signals": {},
        "risk_score": 0.0,
        "risk_level": "",
        "reasons": [],
        "next_step": "",
        "confidence": 1.0,
        "phase_log": [],
        "escalate": False,
        "retry_count": 0,
    }

    run_id = str(uuid.uuid4())
    telemetry = TelemetryCallback()

    try:
        app = build_verification_graph()
        result = app.invoke(
            initial,
            config=RunnableConfig(callbacks=[telemetry], run_name=f"verify-{run_id[:8]}"),
        )

        try:
            validate_state(result)
        except StateValidationError as exc:
            logger.error("State validation failed: %s", exc)
            return SAFE_FALLBACK_RESPONSE

        logger.info("[telemetry] run_id=%s %s", run_id, telemetry.summary())

        formatted = format_response(
            risk_level=result["risk_level"],
            reasons=result["reasons"],
            next_step=result["next_step"],
            phase_log=result["phase_log"],
            escalate=result["escalate"],
            confidence=result["confidence"],
        )

        HistoryStorage().save(run_id, {
            "input_type": input_type,
            "risk_level": formatted["risk_level"],
            "confidence": formatted["confidence"],
            "escalate": formatted["escalate"],
            "input_redacted": redact_pii(user_input[:500]),
        })

        return formatted

    except Exception as exc:
        logger.exception("Verification pipeline failed: %s", exc)
        return SAFE_FALLBACK_RESPONSE
