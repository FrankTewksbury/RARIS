from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from app.config import settings
from app.llm.base import Citation, LLMProvider


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
        response = await self.client.chat.completions.create(**params)
        return response.choices[0].message.content or ""

    async def stream(self, messages: list[dict], **kwargs) -> AsyncIterator[str]:
        response = await self.client.chat.completions.create(
            model=kwargs.get("model", self.model),
            messages=messages,
            temperature=kwargs.get("temperature", 0.2),
            stream=True,
        )
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def complete_grounded(
        self, messages: list[dict], **kwargs
    ) -> tuple[str, list[Citation]]:
        """Generate with OpenAI Responses API web search. Returns (text, citations)."""
        # The Responses API uses 'input' (not 'messages') and a different endpoint.
        # Extract the last user message as input text.
        user_input = messages[-1]["content"] if messages else ""

        response = await self.client.responses.create(
            model=kwargs.get("model", self.model),
            input=user_input,
            tools=[{"type": "web_search"}],
        )

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

        return response.output_text or "", citations
