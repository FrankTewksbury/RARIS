import logging
from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from app.config import settings
from app.llm.base import Citation, LLMProvider
from app.llm.call_logger import LLMCallRecord, log_llm_call_error, log_llm_call_start, log_llm_call_success

logger = logging.getLogger(__name__)

# Reasoning models don't support temperature/top_p sampling parameters
_REASONING_MODEL_PREFIXES = ("o1", "o3", "o4", "gpt-5.2")


def _supports_temperature(model: str) -> bool:
    return not model.startswith(_REASONING_MODEL_PREFIXES)


def _convert_messages(messages: list[dict]) -> list[dict]:
    """Convert standard messages to Responses API input format.

    The Responses API accepts 'system', 'developer', 'user', 'assistant' roles.
    Map 'system' -> 'developer' for best practice (developer instructions).
    """
    converted = []
    for msg in messages:
        role = msg.get("role", "user")
        if role == "system":
            role = "developer"
        converted.append({"role": role, "content": msg.get("content", "")})
    return converted


class OpenAIProvider(LLMProvider):
    def __init__(self, model: str | None = None):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = model or settings.openai_model

    async def complete(self, messages: list[dict], **kwargs) -> str:
        """Generate a complete response using the OpenAI Responses API."""
        model = kwargs.get("model", self.model)
        input_msgs = _convert_messages(messages)

        params: dict = {
            "model": model,
            "input": input_msgs,
        }
        if _supports_temperature(model):
            params["temperature"] = kwargs.get("temperature", 0.2)
        if "max_tokens" in kwargs:
            params["max_output_tokens"] = kwargs["max_tokens"]
        if kwargs.get("response_mime_type") == "application/json":
            params["text"] = {"format": {"type": "json_object"}}

        record = LLMCallRecord(
            provider="openai", model=model, method="complete",
            prompt_chars=sum(len(m.get("content", "")) for m in messages),
            stage=kwargs.get("stage", ""),
        )
        log_llm_call_start(record)
        try:
            response = await self.client.responses.create(**params)
            text = response.output_text or ""
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
        """Stream response tokens using the OpenAI Responses API."""
        model = kwargs.get("model", self.model)
        input_msgs = _convert_messages(messages)

        record = LLMCallRecord(
            provider="openai", model=model, method="stream",
            prompt_chars=sum(len(m.get("content", "")) for m in messages),
            stage=kwargs.get("stage", ""),
        )
        log_llm_call_start(record)
        total_chars = 0
        try:
            stream_params: dict = {
                "model": model,
                "input": input_msgs,
                "stream": True,
            }
            if _supports_temperature(model):
                stream_params["temperature"] = kwargs.get("temperature", 0.2)
            stream = await self.client.responses.create(**stream_params)
            async for event in stream:
                if event.type == "response.output_text.delta":
                    total_chars += len(event.delta)
                    yield event.delta
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
        model = kwargs.get("model", self.model)
        input_msgs = _convert_messages(messages)

        record = LLMCallRecord(
            provider="openai", model=model,
            method="complete_grounded",
            prompt_chars=sum(len(m.get("content", "")) for m in messages),
            stage=kwargs.get("stage", ""),
        )
        log_llm_call_start(record)
        try:
            response = await self.client.responses.create(
                model=model,
                input=input_msgs,
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
