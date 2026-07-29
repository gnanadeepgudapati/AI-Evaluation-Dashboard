# anthropic_adapter.py
# Adapter for Anthropic (Claude) models. Implements the ModelProvider Protocol.

import asyncio
import time

from anthropic import AsyncAnthropic

from providers.base import ModelResponse, redact_secrets


class AnthropicAdapter:
    """Calls Anthropic's Messages API and normalizes the result."""

    async def complete(
        self,
        prompt: str,
        api_key: str,
        model: str,
        timeout_s: float = 30.0,
    ) -> ModelResponse:
        start = time.perf_counter()
        try:
            client = AsyncAnthropic(api_key=api_key)
            response = await asyncio.wait_for(
                client.messages.create(
                    model=model,
                    max_tokens=1024,
                    messages=[{"role": "user", "content": prompt}],
                ),
                timeout=timeout_s,
            )
            latency_ms = (time.perf_counter() - start) * 1000
            text = "".join(
                block.text for block in response.content if block.type == "text"
            )
            return ModelResponse(
                text=text,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                latency_ms=latency_ms,
                error=None,
            )
        except TimeoutError:
            latency_ms = (time.perf_counter() - start) * 1000
            return ModelResponse(
                text="",
                input_tokens=0,
                output_tokens=0,
                latency_ms=latency_ms,
                error=f"Anthropic request timed out after {timeout_s}s",
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            return ModelResponse(
                text="",
                input_tokens=0,
                output_tokens=0,
                latency_ms=latency_ms,
                error=redact_secrets(f"{type(exc).__name__}: {exc}"),
            )
