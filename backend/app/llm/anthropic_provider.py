import logging
from collections.abc import AsyncIterator

import anthropic

from app.config import settings
from app.llm.base import Citation, LLMProvider
from app.llm.call_logger import LLMCallRecord, log_llm_call_error, log_llm_call_start, log_llm_call_success

logger = logging.getLogger(__name__)


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

        record = LLMCallRecord(
            provider="anthropic", model=params["model"], method="complete",
            prompt_chars=sum(len(m.get("content", "")) for m in messages),
            stage=kwargs.get("stage", ""),
        )
        log_llm_call_start(record)
        try:
            # Use streaming to avoid Anthropic 10-min timeout on long requests
            chunks: list[str] = []
            async with self.client.messages.stream(**params) as stream:
                async for chunk in stream.text_stream:
                    chunks.append(chunk)
            text = "".join(chunks)
            record.finish(response_chars=len(text))
            log_llm_call_success(record)
            return text
        except Exception as exc:
            record.finish()
            record.error_message = str(exc)
            record.error_code = getattr(exc, "status_code", None)
            log_llm_call_error(record)
            raise

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

        record = LLMCallRecord(
            provider="anthropic", model=params["model"], method="stream",
            prompt_chars=sum(len(m.get("content", "")) for m in messages),
            stage=kwargs.get("stage", ""),
        )
        log_llm_call_start(record)
        total_chars = 0
        try:
            async with self.client.messages.stream(**params) as stream:
                async for text in stream.text_stream:
                    total_chars += len(text)
                    yield text
            record.finish(response_chars=total_chars)
            log_llm_call_success(record)
        except Exception as exc:
            record.finish()
            record.error_message = str(exc)
            record.error_code = getattr(exc, "status_code", None)
            log_llm_call_error(record)
            raise

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

        record = LLMCallRecord(
            provider="anthropic", model=params["model"], method="complete_grounded",
            prompt_chars=sum(len(m.get("content", "")) for m in messages),
            stage=kwargs.get("stage", ""),
        )
        log_llm_call_start(record)
        try:
            response = await self.client.messages.create(**params)
        except Exception as exc:
            record.finish()
            record.error_message = str(exc)
            record.error_code = getattr(exc, "status_code", None)
            log_llm_call_error(record)
            raise

        text_parts: list[str] = []
        citations: list[Citation] = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
                for annotation in getattr(block, "annotations", None) or []:
                    if getattr(annotation, "type", None) == "web_citation":
                        citations.append(
                            Citation(
                                url=getattr(annotation, "url", "") or "",
                                title=getattr(annotation, "title", "") or "",
                            )
                        )

        text = "\n".join(text_parts)
        record.finish(response_chars=len(text))
        log_llm_call_success(record)
        return text, citations
