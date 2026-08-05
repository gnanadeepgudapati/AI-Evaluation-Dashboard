# openai_adapter.py
# Adapter for OpenAI (GPT) models. Implements the ModelProvider Protocol.

import asyncio
import time

from openai import AsyncOpenAI

from providers.base import ModelResponse, redact_secrets


class OpenAIAdapter:
    """Calls OpenAI's Chat Completions API and normalizes the result."""

    async def complete(
        self,
        prompt: str,
        api_key: str,
        model: str,
        timeout_s: float = 30.0,
    ) -> ModelResponse:
        start = time.perf_counter()
        try:
            client = AsyncOpenAI(api_key=api_key)
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                ),
                timeout=timeout_s,
            )
            latency_ms = (time.perf_counter() - start) * 1000
            text = response.choices[0].message.content or ""
            usage = response.usage
            return ModelResponse(
                text=text,
                input_tokens=usage.prompt_tokens if usage else 0,
                output_tokens=usage.completion_tokens if usage else 0,
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
                error=f"OpenAI request timed out after {timeout_s}s",
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            return ModelResponse(
                text="",
                input_tokens=0,
                output_tokens=0,
                latency_ms=latency_ms,
                error=redact_secrets(f"{type(exc).__name__}: {exc}", secret=api_key),
            )
