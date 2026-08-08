# shared/telemetry.py
import time
from typing import Any, Dict, List, Optional
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

# Claude Sonnet 5 pricing (USD per million tokens)
_PRICE_INPUT_PER_M = 3.00
_PRICE_OUTPUT_PER_M = 15.00


class TelemetryCallback(BaseCallbackHandler):
    """Captures per-LLM-call token counts, latency, and estimated cost."""

    def __init__(self):
        super().__init__()
        self.reset()

    def reset(self):
        self.llm_calls: int = 0
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self._call_start: Optional[float] = None
        self.llm_latency_ms: float = 0.0

    def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs) -> None:
        self._call_start = time.time()

    def on_llm_end(self, response: LLMResult, **kwargs) -> None:
        if self._call_start is not None:
            self.llm_latency_ms += (time.time() - self._call_start) * 1000
            self._call_start = None

        self.llm_calls += 1

        for generation_list in response.generations:
            for gen in generation_list:
                usage = None
                if hasattr(gen, "message") and hasattr(gen.message, "usage_metadata"):
                    usage = gen.message.usage_metadata
                elif hasattr(gen, "generation_info") and gen.generation_info:
                    usage = gen.generation_info.get("usage", {})

                if usage:
                    self.input_tokens += getattr(usage, "input_tokens", 0) or usage.get("input_tokens", 0)
                    self.output_tokens += getattr(usage, "output_tokens", 0) or usage.get("output_tokens", 0)

    @property
    def estimated_cost_usd(self) -> float:
        return (
            (self.input_tokens / 1_000_000) * _PRICE_INPUT_PER_M
            + (self.output_tokens / 1_000_000) * _PRICE_OUTPUT_PER_M
        )

    def summary(self) -> Dict[str, Any]:
        return {
            "LLM Calls": self.llm_calls,
            "Input Tokens": self.input_tokens,
            "Output Tokens": self.output_tokens,
            "Est. Cost ($)": f"${self.estimated_cost_usd:.4f}",
            "LLM Time (s)": f"{self.llm_latency_ms / 1000:.2f}"
        }
