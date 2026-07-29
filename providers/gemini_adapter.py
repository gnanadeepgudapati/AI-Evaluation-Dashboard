# gemini_adapter.py
# Adapter for Google Gemini models. Implements the ModelProvider Protocol.

import asyncio
import time

import google.generativeai as genai

from providers.base import ModelResponse, redact_secrets


class GeminiAdapter:
    """Calls Google's Gemini API and normalizes the result."""

    async def complete(
        self,
        prompt: str,
        api_key: str,
        model: str,
        timeout_s: float = 30.0,
    ) -> ModelResponse:
        start = time.perf_counter()
        try:
            genai.configure(api_key=api_key)
            model_obj = genai.GenerativeModel(model)
            response = await asyncio.wait_for(
                model_obj.generate_content_async(prompt),
                timeout=timeout_s,
            )
            latency_ms = (time.perf_counter() - start) * 1000
            usage = response.usage_metadata
            return ModelResponse(
                text=response.text or "",
                input_tokens=usage.prompt_token_count if usage else 0,
                output_tokens=usage.candidates_token_count if usage else 0,
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
                error=f"Gemini request timed out after {timeout_s}s",
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
