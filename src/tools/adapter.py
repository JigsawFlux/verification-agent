# src/tools/adapter.py
import logging
from typing import Callable, Dict

logger = logging.getLogger(__name__)

# Registry maps tool names to callables with signature (content: str) -> dict
_registry: Dict[str, Callable[[str], dict]] = {}


def register(name: str):
    """Decorator to register a tool function by name."""
    def decorator(fn: Callable[[str], dict]) -> Callable[[str], dict]:
        _registry[name] = fn
        return fn
    return decorator


class ToolRegistry:
    """Stable adapter interface — callers interact only through this class."""

    @staticmethod
    def run(name: str, content: str) -> dict:
        """
        Run a named tool against content.
        Returns a result dict with at least {"tool": name, "error": ...} on failure.
        """
        if name not in _registry:
            logger.error("Unknown tool: %s", name)
            return {"tool": name, "error": f"Unknown tool '{name}'"}
        try:
            result = _registry[name](content)
            result["tool"] = name
            return result
        except Exception as exc:
            logger.exception("Tool '%s' failed", name)
            return {"tool": name, "error": str(exc)}

    @staticmethod
    def available() -> list[str]:
        return list(_registry.keys())


# Import tool modules so their @register decorators fire at import time
def _load_tools():
    from src.tools import (  # noqa: F401
        source_credibility,
        manipulation_language,
        cross_check,
        privacy_risk,
    )

_load_tools()
