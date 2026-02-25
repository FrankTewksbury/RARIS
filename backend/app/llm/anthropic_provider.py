from collections.abc import AsyncIterator

import anthropic

from app.config import settings
from app.llm.base import LLMProvider


class AnthropicProvider(LLMProvider):
    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = model

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
