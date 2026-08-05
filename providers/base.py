# base.py
# Shared contract every provider adapter must implement.
# The arena backend depends only on this Protocol — never on a specific SDK.

import re
from dataclasses import dataclass
from typing import Protocol

# Generic patterns for redacting API keys from error messages before they are
# logged or returned to the client. Never let a raw key reach a log line.
#
# The character classes MUST include "-" and "_": every current vendor format
# puts a hyphenated segment between the prefix and the random part
# (sk-proj-..., sk-svcacct-..., sk-ant-api03-...). A class of [A-Za-z0-9] stops
# at the first hyphen, so the length floor is never reached and the whole key
# passes through unredacted.
_REDACTION_PATTERNS = [
    # Anthropic: sk-ant-api03-...
    re.compile(r"sk-ant-[A-Za-z0-9\-_]{10,}"),
    # OpenAI: legacy sk-..., plus sk-proj- / sk-svcacct- / sk-admin- variants.
    re.compile(r"sk-[A-Za-z0-9\-_]{20,}"),
    # Google AI Studio / Gemini: AIza + ~35 chars. Open-ended, not a fixed
    # length, so a longer key can't leave a readable tail behind.
    re.compile(r"AIza[A-Za-z0-9\-_]{30,}"),
    # Groq — this is the server's own judge key, not a BYOK user key.
    re.compile(r"gsk_[A-Za-z0-9\-_]{20,}"),
]

# Below this length a "secret" is a placeholder or empty string, and blanket
# substitution would mangle ordinary error text.
_MIN_SECRET_LEN = 8


def redact_secrets(text: str, secret: str | None = None) -> str:
    """Replace anything that looks like an API key with a redacted marker.

    When the caller knows the exact secret in play it should pass `secret`.
    That match is format-agnostic, so it still holds if a vendor changes its
    key shape or a provider is added whose format no pattern below covers.
    The patterns remain as a backstop for keys we were never handed — most
    importantly the server's own Groq key.
    """
    redacted = text
    if secret and len(secret) >= _MIN_SECRET_LEN:
        redacted = redacted.replace(secret, "[REDACTED]")
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
