from collections.abc import AsyncIterator

import anthropic

from app.config import settings
from app.llm.base import Citation, LLMProvider


class AnthropicProvider(LLMProvider):
    def __init__(self, model: str | None = None):
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = model or settings.anthropic_model

    async def complete(self, messages: list[dict], **kwargs) -> str:
        system_msg = None
        chat_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                chat_messages.append(msg)

        params = {
            "model": kwargs.get("model", self.model),
            "max_tokens": kwargs.get("max_tokens", 4096),
            "messages": chat_messages,
        }
        if system_msg:
            params["system"] = system_msg

        response = await self.client.messages.create(**params)
        return response.content[0].text

    async def stream(self, messages: list[dict], **kwargs) -> AsyncIterator[str]:
        system_msg = None
        chat_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                chat_messages.append(msg)

        params = {
            "model": kwargs.get("model", self.model),
            "max_tokens": kwargs.get("max_tokens", 4096),
            "messages": chat_messages,
        }
        if system_msg:
            params["system"] = system_msg

        async with self.client.messages.stream(**params) as stream:
            async for text in stream.text_stream:
                yield text

    def _split_system(self, messages: list[dict]) -> tuple[str | None, list[dict]]:
        """Separate system message from chat messages."""
        system_msg = None
        chat_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                chat_messages.append(msg)
        return system_msg, chat_messages

    async def complete_grounded(
        self, messages: list[dict], **kwargs
    ) -> tuple[str, list[Citation]]:
        """Generate with Anthropic web search tool. Returns (text, citations)."""
        system_msg, chat_messages = self._split_system(messages)

        params: dict = {
            "model": kwargs.get("model", self.model),
            "max_tokens": kwargs.get("max_tokens", 4096),
            "messages": chat_messages,
            "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
        }
        if system_msg:
            params["system"] = system_msg

        response = await self.client.messages.create(**params)

        text_parts: list[str] = []
        citations: list[Citation] = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
                # Extract citations from text block annotations if present
                for annotation in getattr(block, "annotations", None) or []:
                    if getattr(annotation, "type", None) == "web_citation":
                        citations.append(
                            Citation(
                                url=getattr(annotation, "url", "") or "",
                                title=getattr(annotation, "title", "") or "",
                            )
                        )

        return "\n".join(text_parts), citations
