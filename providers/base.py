# base.py
# Shared contract every provider adapter must implement.
# The arena backend depends only on this Protocol — never on a specific SDK.

import re
from dataclasses import dataclass
from typing import Protocol

# Generic patterns for redacting API keys from error messages before they are
# logged or returned to the client. Never let a raw key reach a log line.
_REDACTION_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9\-_]{10,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AIza[A-Za-z0-9\-_]{35}"),
]


def redact_secrets(text: str) -> str:
    """Replace anything that looks like an API key with a redacted marker."""
    redacted = text
    for pattern in _REDACTION_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


@dataclass
class ModelResponse:
    """Normalized result from any provider adapter."""

    text: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    error: str | None = None


class ModelProvider(Protocol):
    """Every adapter (Anthropic, OpenAI, Gemini) implements this contract."""

    async def complete(
        self,
        prompt: str,
        api_key: str,
        model: str,
        timeout_s: float = 30.0,
    ) -> ModelResponse:
        ...
