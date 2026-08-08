# tests/conftest.py
import sys
import os
import pytest

# Ensure project root is on sys.path so imports work without install
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Minimal env so llm.py doesn't crash on import in unit tests.
# CLAUDE_MODEL here is only a guard so the import doesn't raise;
# all tool tests patch get_llm() with FakeLLM and never reach the real API.
os.environ.setdefault("LLM_PROVIDER", "anthropic")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-unit-tests")
os.environ.setdefault("CLAUDE_MODEL", "claude-sonnet-5")


class FakeResp:
    """Minimal stand-in for a langchain chat response."""
    def __init__(self, content: str):
        self.content = content


class FakeLLM:
    """Reusable LLM stub for all tool unit tests.

    Usage:
        monkeypatch.setattr(module_under_test, "get_llm", lambda **_: FakeLLM(json_str))
    """
    def __init__(self, content: str):
        self._content = content

    def invoke(self, _messages):
        return FakeResp(self._content)


@pytest.fixture
def fake_llm_factory():
    """Return a factory: fake_llm_factory(json_str) → FakeLLM instance."""
    return FakeLLM
