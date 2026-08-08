# src/tools/_shared.py
"""
Shared parsing utilities used by all four specialist tools.

Centralised here so the logic (especially _extract_json's raw_decode loop)
has one canonical implementation that every tool imports.
"""
import json
import re


def _extract_json(raw: str) -> str:
    """Extract the first syntactically complete JSON object from an LLM response."""
    text = (raw or "").strip()

    # Fenced block takes priority; non-greedy .*? backtracks to satisfy closing ```
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fenced:
        return fenced.group(1).strip()

    # Bare JSON array is not the expected shape — return as-is so the
    # isinstance(parsed, dict) check in the caller fails cleanly
    if text.startswith("["):
        return text

    # raw_decode finds the first syntactically complete object; avoids greedy
    # regex that would span multiple {…} fragments in prose
    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch == "{":
            try:
                obj, end = decoder.raw_decode(text[i:])
                if isinstance(obj, dict):
                    return text[i : i + end]
            except Exception:
                continue

    return text


def _as_bool(value, fallback: bool) -> bool:
    """Safely coerce JSON booleans, string variants, or None to Python bool."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        s = value.strip().lower()
        if s in {"true", "1", "yes", "y"}:
            return True
        if s in {"false", "0", "no", "n"}:
            return False
    if value is None:
        return fallback
    return bool(value)


def _clamp01(value, fallback: float) -> float:
    """Cast value to float and clamp to [0.0, 1.0]; return fallback on failure."""
    try:
        v = float(value)
        return max(0.0, min(1.0, v))
    except Exception:
        return fallback
