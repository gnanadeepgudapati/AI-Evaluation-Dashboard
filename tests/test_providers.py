# test_providers.py
# Provider adapters must never call a real, paid API in tests. Every SDK
# client is mocked at the module boundary.

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from providers.anthropic_adapter import AnthropicAdapter
from providers.base import redact_secrets
from providers.gemini_adapter import GeminiAdapter
from providers.openai_adapter import OpenAIAdapter

# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_anthropic_adapter_success():
    mock_response = MagicMock()
    mock_response.content = [MagicMock(type="text", text="Hello from Claude")]
    mock_response.usage = MagicMock(input_tokens=12, output_tokens=34)

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    with patch("providers.anthropic_adapter.AsyncAnthropic", return_value=mock_client):
        adapter = AnthropicAdapter()
        result = await adapter.complete(
            prompt="hi", api_key="sk-ant-test-key-0000000000", model="claude-3-5-haiku-20241022"
        )

    assert result.text == "Hello from Claude"
    assert result.input_tokens == 12
    assert result.output_tokens == 34
    assert result.error is None
    assert result.latency_ms >= 0


@pytest.mark.asyncio
async def test_anthropic_adapter_error_redacts_key():
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(
        side_effect=RuntimeError("auth failed for key sk-ant-abcdefghijklmnopqrst1234")
    )

    with patch("providers.anthropic_adapter.AsyncAnthropic", return_value=mock_client):
        adapter = AnthropicAdapter()
        result = await adapter.complete(
            prompt="hi", api_key="sk-ant-abcdefghijklmnopqrst1234", model="claude-3-5-haiku-20241022"
        )

    assert result.error is not None
    assert "sk-ant-" not in result.error
    assert "[REDACTED]" in result.error
    assert result.text == ""


@pytest.mark.asyncio
async def test_anthropic_adapter_timeout():
    async def slow_create(*args, **kwargs):
        await asyncio.sleep(0.2)
        return MagicMock()

    mock_client = MagicMock()
    mock_client.messages.create = slow_create

    with patch("providers.anthropic_adapter.AsyncAnthropic", return_value=mock_client):
        adapter = AnthropicAdapter()
        result = await adapter.complete(
            prompt="hi", api_key="sk-ant-test", model="claude-3-5-haiku-20241022", timeout_s=0.01
        )

    assert result.error is not None
    assert "timed out" in result.error


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_openai_adapter_success():
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="Hello from GPT"))]
    mock_response.usage = MagicMock(prompt_tokens=8, completion_tokens=16)

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("providers.openai_adapter.AsyncOpenAI", return_value=mock_client):
        adapter = OpenAIAdapter()
        result = await adapter.complete(prompt="hi", api_key="sk-test1234567890123456789", model="gpt-4o-mini")

    assert result.text == "Hello from GPT"
    assert result.input_tokens == 8
    assert result.output_tokens == 16
    assert result.error is None


@pytest.mark.asyncio
async def test_openai_adapter_error_redacts_key():
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=RuntimeError("invalid key sk-abcdefghijklmnopqrstuvwxyz123456")
    )

    with patch("providers.openai_adapter.AsyncOpenAI", return_value=mock_client):
        adapter = OpenAIAdapter()
        result = await adapter.complete(
            prompt="hi", api_key="sk-abcdefghijklmnopqrstuvwxyz123456", model="gpt-4o-mini"
        )

    assert result.error is not None
    assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in result.error
    assert "[REDACTED]" in result.error


@pytest.mark.asyncio
async def test_openai_adapter_timeout():
    async def slow_create(*args, **kwargs):
        await asyncio.sleep(0.2)
        return MagicMock()

    mock_client = MagicMock()
    mock_client.chat.completions.create = slow_create

    with patch("providers.openai_adapter.AsyncOpenAI", return_value=mock_client):
        adapter = OpenAIAdapter()
        result = await adapter.complete(prompt="hi", api_key="sk-test", model="gpt-4o-mini", timeout_s=0.01)

    assert result.error is not None
    assert "timed out" in result.error


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gemini_adapter_success():
    mock_response = MagicMock()
    mock_response.text = "Hello from Gemini"
    mock_response.usage_metadata = MagicMock(prompt_token_count=5, candidates_token_count=9)

    mock_model_obj = MagicMock()
    mock_model_obj.generate_content_async = AsyncMock(return_value=mock_response)

    with patch("providers.gemini_adapter.genai.configure"), patch(
        "providers.gemini_adapter.genai.GenerativeModel", return_value=mock_model_obj
    ):
        adapter = GeminiAdapter()
        result = await adapter.complete(prompt="hi", api_key="AIzaTestKey", model="gemini-1.5-flash")

    assert result.text == "Hello from Gemini"
    assert result.input_tokens == 5
    assert result.output_tokens == 9
    assert result.error is None


@pytest.mark.asyncio
async def test_gemini_adapter_error_redacts_key():
    mock_model_obj = MagicMock()
    mock_model_obj.generate_content_async = AsyncMock(
        side_effect=RuntimeError("bad key AIzaSyABCDEFGHIJKLMNOPQRSTUVWXYZ1234567")
    )

    with patch("providers.gemini_adapter.genai.configure"), patch(
        "providers.gemini_adapter.genai.GenerativeModel", return_value=mock_model_obj
    ):
        adapter = GeminiAdapter()
        result = await adapter.complete(
            prompt="hi", api_key="AIzaSyABCDEFGHIJKLMNOPQRSTUVWXYZ1234567", model="gemini-1.5-flash"
        )

    assert result.error is not None
    assert "AIzaSyABCDEFGHIJKLMNOPQRSTUVWXYZ1234567" not in result.error
    assert "[REDACTED]" in result.error


@pytest.mark.asyncio
async def test_gemini_adapter_timeout():
    async def slow_generate(*args, **kwargs):
        await asyncio.sleep(0.2)
        return MagicMock()

    mock_model_obj = MagicMock()
    mock_model_obj.generate_content_async = slow_generate

    with patch("providers.gemini_adapter.genai.configure"), patch(
        "providers.gemini_adapter.genai.GenerativeModel", return_value=mock_model_obj
    ):
        adapter = GeminiAdapter()
        result = await adapter.complete(
            prompt="hi", api_key="AIzaTest", model="gemini-1.5-flash", timeout_s=0.01
        )

    assert result.error is not None
    assert "timed out" in result.error


# ---------------------------------------------------------------------------
# Secret redaction
#
# An unredacted key in ModelResponse.error does not stay in memory: it is
# persisted to arena_store and served back out of the *unauthenticated*
# GET /runs/{run_id} endpoint. Every real key format must be covered.
# ---------------------------------------------------------------------------

# Fake values, real formats.
_REAL_KEY_FORMATS = [
    ("openai_legacy", "sk-" + "A" * 48),
    ("openai_project", "sk-proj-" + "aB3" * 10 + "_xY-9"),
    ("openai_service_account", "sk-svcacct-" + "kL7" * 12),
    ("openai_admin", "sk-admin-" + "pQ2" * 12),
    ("anthropic", "sk-ant-api03-" + "qR4" * 15 + "-AA"),
    ("gemini", "AIza" + "S" * 35),
    ("gemini_longer", "AIza" + "S" * 39),
    ("groq_server_key", "gsk_" + "zM8" * 14),
]


@pytest.mark.parametrize("label,key", _REAL_KEY_FORMATS, ids=[label for label, _ in _REAL_KEY_FORMATS])
def test_redact_secrets_covers_every_real_key_format(label, key):
    message = f"AuthenticationError: invalid key {key} provided"

    result = redact_secrets(message)

    assert key not in result, f"{label} key leaked verbatim"
    assert "[REDACTED]" in result


@pytest.mark.parametrize("label,key", _REAL_KEY_FORMATS, ids=[label for label, _ in _REAL_KEY_FORMATS])
def test_redact_secrets_removes_known_key_regardless_of_format(label, key):
    """When the caller knows the exact secret, redaction must not depend on
    the value matching any pattern."""
    message = f"boom: {key} and an unknown-vendor key xyz_{'Q' * 40}"

    result = redact_secrets(message, secret=key)

    assert key not in result


def test_redact_secrets_ignores_short_or_empty_secret():
    """A too-short 'secret' must not blank out ordinary error text."""
    assert redact_secrets("connection refused", secret="") == "connection refused"
    assert redact_secrets("connection refused", secret="abc") == "connection refused"


def test_redact_secrets_leaves_clean_text_untouched():
    assert redact_secrets("RateLimitError: too many requests") == (
        "RateLimitError: too many requests"
    )


@pytest.mark.asyncio
async def test_openai_adapter_redacts_modern_project_key():
    leaked_key = "sk-proj-" + "aB3" * 20 + "_xY-9"
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=RuntimeError(f"invalid_api_key: {leaked_key}")
    )

    with patch("providers.openai_adapter.AsyncOpenAI", return_value=mock_client):
        adapter = OpenAIAdapter()
        result = await adapter.complete(prompt="hi", api_key=leaked_key, model="gpt-4o-mini")

    assert result.error is not None
    assert leaked_key not in result.error
    assert "[REDACTED]" in result.error
