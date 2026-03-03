import logging
from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from app.config import settings
from app.llm.base import Citation, LLMProvider
from app.llm.call_logger import LLMCallRecord, log_llm_call_error, log_llm_call_start, log_llm_call_success

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    def __init__(self, model: str = "gpt-5.2-pro"):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = model

    async def complete(self, messages: list[dict], **kwargs) -> str:
        params = {
            "model": kwargs.get("model", self.model),
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.2),
        }
        if "max_tokens" in kwargs:
            params["max_tokens"] = kwargs["max_tokens"]

        record = LLMCallRecord(
            provider="openai", model=params["model"], method="complete",
            prompt_chars=sum(len(m.get("content", "")) for m in messages),
            stage=kwargs.get("stage", ""),
        )
        log_llm_call_start(record)
        try:
            response = await self.client.chat.completions.create(**params)
            text = response.choices[0].message.content or ""
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
        record = LLMCallRecord(
            provider="openai", model=kwargs.get("model", self.model), method="stream",
            prompt_chars=sum(len(m.get("content", "")) for m in messages),
            stage=kwargs.get("stage", ""),
        )
        log_llm_call_start(record)
        total_chars = 0
        try:
            response = await self.client.chat.completions.create(
                model=kwargs.get("model", self.model),
                messages=messages,
                temperature=kwargs.get("temperature", 0.2),
                stream=True,
            )
            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    total_chars += len(content)
                    yield content
            record.finish(response_chars=total_chars)
            log_llm_call_success(record)
        except Exception as exc:
            record.finish()
            record.error_message = str(exc)
            record.error_code = getattr(exc, "status_code", None)
            log_llm_call_error(record)
            raise

    async def complete_grounded(
        self, messages: list[dict], **kwargs
    ) -> tuple[str, list[Citation]]:
        """Generate with OpenAI Responses API web search. Returns (text, citations)."""
        user_input = messages[-1]["content"] if messages else ""

        record = LLMCallRecord(
            provider="openai", model=kwargs.get("model", self.model),
            method="complete_grounded",
            prompt_chars=len(user_input),
            stage=kwargs.get("stage", ""),
        )
        log_llm_call_start(record)
        try:
            response = await self.client.responses.create(
                model=kwargs.get("model", self.model),
                input=user_input,
                tools=[{"type": "web_search"}],
            )
        except Exception as exc:
            record.finish()
            record.error_message = str(exc)
            record.error_code = getattr(exc, "status_code", None)
            log_llm_call_error(record)
            raise

        citations: list[Citation] = []
        for item in response.output:
            if getattr(item, "type", None) == "message":
                for content_block in getattr(item, "content", []):
                    for annotation in getattr(content_block, "annotations", []):
                        if getattr(annotation, "type", None) == "url_citation":
                            citations.append(
                                Citation(
                                    url=getattr(annotation, "url", "") or "",
                                    title=getattr(annotation, "title", "") or "",
                                )
                            )

        text = response.output_text or ""
        record.finish(response_chars=len(text))
        log_llm_call_success(record)
        return text, citations
