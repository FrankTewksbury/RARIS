"""Tests for LLM provider grounding support (complete_grounded)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.llm.base import Citation, LLMProvider
from app.llm.gemini_provider import GeminiProvider
from app.llm.anthropic_provider import AnthropicProvider
from app.llm.openai_provider import OpenAIProvider


# ---------------------------------------------------------------------------
# Citation dataclass
# ---------------------------------------------------------------------------

def test_citation_defaults():
    c = Citation(url="https://example.com")
    assert c.url == "https://example.com"
    assert c.title == ""


def test_citation_with_title():
    c = Citation(url="https://example.com", title="Example")
    assert c.title == "Example"


# ---------------------------------------------------------------------------
# Base LLMProvider — default complete_grounded falls back to complete()
# ---------------------------------------------------------------------------

class StubProvider(LLMProvider):
    async def complete(self, messages, **kwargs):
        return "stub response"

    async def stream(self, messages, **kwargs):
        yield "stub"


@pytest.mark.asyncio
async def test_base_provider_grounded_fallback():
    provider = StubProvider()
    text, citations = await provider.complete_grounded(
        [{"role": "user", "content": "test"}]
    )
    assert text == "stub response"
    assert citations == []


# ---------------------------------------------------------------------------
# GeminiProvider.complete_grounded
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gemini_grounded_adds_google_search_tool():
    """Verify that complete_grounded injects google_search tool into config."""
    with patch("app.llm.gemini_provider.genai") as mock_genai:
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        # Build a mock response with grounding metadata
        mock_web = MagicMock()
        mock_web.uri = "https://tdhca.state.tx.us/dpa"
        mock_web.title = "Texas DPA Programs"

        mock_chunk = MagicMock()
        mock_chunk.web = mock_web

        mock_gm = MagicMock()
        mock_gm.grounding_chunks = [mock_chunk]

        mock_candidate = MagicMock()
        mock_candidate.grounding_metadata = mock_gm

        mock_response = MagicMock()
        mock_response.text = "Texas has several DPA programs."
        mock_response.candidates = [mock_candidate]

        # Wire up async call
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        provider = GeminiProvider.__new__(GeminiProvider)
        provider.client = mock_client
        provider.model = "gemini-3.1-pro-preview"
        provider._fallback_chain = ["gemini-3.1-pro-preview"]

        text, citations = await provider.complete_grounded(
            [{"role": "user", "content": "Find DPA programs in Texas"}]
        )

        assert text == "Texas has several DPA programs."
        assert len(citations) == 1
        assert citations[0].url == "https://tdhca.state.tx.us/dpa"
        assert citations[0].title == "Texas DPA Programs"

        # Verify google_search tool was passed in config
        call_args = mock_client.aio.models.generate_content.call_args
        config = call_args.kwargs["config"]
        assert config.tools is not None
        assert len(config.tools) == 1


@pytest.mark.asyncio
async def test_gemini_grounded_no_metadata():
    """Handles response without grounding metadata gracefully."""
    with patch("app.llm.gemini_provider.genai") as mock_genai:
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        mock_candidate = MagicMock()
        mock_candidate.grounding_metadata = None

        mock_response = MagicMock()
        mock_response.text = "No grounding available."
        mock_response.candidates = [mock_candidate]

        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        provider = GeminiProvider.__new__(GeminiProvider)
        provider.client = mock_client
        provider.model = "gemini-3.1-pro-preview"
        provider._fallback_chain = ["gemini-3.1-pro-preview"]

        text, citations = await provider.complete_grounded(
            [{"role": "user", "content": "test"}]
        )

        assert text == "No grounding available."
        assert citations == []


# ---------------------------------------------------------------------------
# AnthropicProvider.complete_grounded
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_anthropic_grounded_returns_text_and_citations():
    """Verify Anthropic grounded call parses text blocks and annotations."""
    with patch("app.llm.anthropic_provider.anthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_anthropic.AsyncAnthropic.return_value = mock_client

        # Build mock response with text block + web citations
        mock_annotation = MagicMock()
        mock_annotation.type = "web_citation"
        mock_annotation.url = "https://hud.gov/dpa"
        mock_annotation.title = "HUD DPA Guide"

        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = "HUD offers several DPA programs."
        mock_text_block.annotations = [mock_annotation]

        mock_response = MagicMock()
        mock_response.content = [mock_text_block]

        mock_client.messages.create = AsyncMock(return_value=mock_response)

        provider = AnthropicProvider.__new__(AnthropicProvider)
        provider.client = mock_client
        provider.model = "claude-sonnet-4-6"

        text, citations = await provider.complete_grounded(
            [{"role": "user", "content": "Find DPA programs"}]
        )

        assert text == "HUD offers several DPA programs."
        assert len(citations) == 1
        assert citations[0].url == "https://hud.gov/dpa"

        # Verify web_search tool was included
        call_args = mock_client.messages.create.call_args
        tools = call_args.kwargs.get("tools") or call_args[1].get("tools")
        assert any(t.get("type", "").startswith("web_search") for t in tools)


@pytest.mark.asyncio
async def test_anthropic_grounded_system_message():
    """System messages are correctly separated for the Anthropic API."""
    with patch("app.llm.anthropic_provider.anthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_anthropic.AsyncAnthropic.return_value = mock_client

        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = "result"
        mock_text_block.annotations = []

        mock_response = MagicMock()
        mock_response.content = [mock_text_block]

        mock_client.messages.create = AsyncMock(return_value=mock_response)

        provider = AnthropicProvider.__new__(AnthropicProvider)
        provider.client = mock_client
        provider.model = "claude-sonnet-4-6"

        await provider.complete_grounded([
            {"role": "system", "content": "You are a DPA expert."},
            {"role": "user", "content": "Find programs"},
        ])

        call_args = mock_client.messages.create.call_args
        assert call_args.kwargs.get("system") or call_args[1].get("system")


# ---------------------------------------------------------------------------
# OpenAIProvider.complete_grounded
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_openai_grounded_returns_text_and_citations():
    """Verify OpenAI grounded call uses Responses API and parses citations."""
    with patch("app.llm.openai_provider.AsyncOpenAI") as MockOpenAI:
        mock_client = AsyncMock()
        MockOpenAI.return_value = mock_client

        # Build mock Responses API output
        mock_annotation = MagicMock()
        mock_annotation.type = "url_citation"
        mock_annotation.url = "https://nhc.org/dpa"
        mock_annotation.title = "NHC DPA Resources"

        mock_content = MagicMock()
        mock_content.annotations = [mock_annotation]

        mock_message = MagicMock()
        mock_message.type = "message"
        mock_message.content = [mock_content]

        mock_response = MagicMock()
        mock_response.output = [mock_message]
        mock_response.output_text = "NHC has DPA resources."

        mock_client.responses.create = AsyncMock(return_value=mock_response)

        provider = OpenAIProvider.__new__(OpenAIProvider)
        provider.client = mock_client
        provider.model = "gpt-5.2-pro"

        text, citations = await provider.complete_grounded(
            [{"role": "user", "content": "Find DPA resources"}]
        )

        assert text == "NHC has DPA resources."
        assert len(citations) == 1
        assert citations[0].url == "https://nhc.org/dpa"
        assert citations[0].title == "NHC DPA Resources"

        # Verify web_search tool was passed
        call_args = mock_client.responses.create.call_args
        tools = call_args.kwargs.get("tools") or call_args[1].get("tools")
        assert any(t.get("type") == "web_search" for t in tools)


@pytest.mark.asyncio
async def test_openai_grounded_no_citations():
    """OpenAI response without citations returns empty list."""
    with patch("app.llm.openai_provider.AsyncOpenAI") as MockOpenAI:
        mock_client = AsyncMock()
        MockOpenAI.return_value = mock_client

        mock_message = MagicMock()
        mock_message.type = "message"
        mock_message.content = []

        mock_response = MagicMock()
        mock_response.output = [mock_message]
        mock_response.output_text = "General response."

        mock_client.responses.create = AsyncMock(return_value=mock_response)

        provider = OpenAIProvider.__new__(OpenAIProvider)
        provider.client = mock_client
        provider.model = "gpt-5.2-pro"

        text, citations = await provider.complete_grounded(
            [{"role": "user", "content": "test"}]
        )

        assert text == "General response."
        assert citations == []
