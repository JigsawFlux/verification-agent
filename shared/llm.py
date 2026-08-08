# shared/llm.py
import os
from langchain_core.language_models.chat_models import BaseChatModel


def get_llm(temperature: float = 0.1) -> BaseChatModel:
    """
    Return a chat model based on the LLM_PROVIDER environment variable.

    Supported providers:
      - 'anthropic' (default): uses langchain_anthropic.ChatAnthropic
      - 'ollama': uses langchain_ollama.ChatOllama (requires local Ollama service)

    Environment variables:
      LLM_PROVIDER      — 'anthropic' or 'ollama' (default: 'anthropic')
      CLAUDE_MODEL      — Anthropic model ID (default: 'claude-sonnet-5')
      ANTHROPIC_API_KEY — Required for Anthropic provider
      OLLAMA_MODEL      — Ollama model name (default: 'llama3.1')
      OLLAMA_BASE_URL   — Ollama service URL (default: 'http://localhost:11434')
    """
    provider = os.environ.get("LLM_PROVIDER", "anthropic").lower()

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-5"),
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
            temperature=temperature
        )

    if provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=os.environ.get("OLLAMA_MODEL", "llama3.1"),
            base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
            temperature=temperature
        )

    raise ValueError(
        f"Unsupported LLM_PROVIDER: '{provider}'. Supported values: 'anthropic', 'ollama'."
    )
