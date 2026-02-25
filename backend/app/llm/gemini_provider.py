from collections.abc import AsyncIterator

from google import genai

from app.config import settings
from app.llm.base import LLMProvider


class GeminiProvider(LLMProvider):
    def __init__(self, model: str = "gemini-2.0-flash"):
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model = model

    async def complete(self, messages: list[dict], **kwargs) -> str:
        contents = []
        for msg in messages:
            role = "model" if msg["role"] == "assistant" else "user"
            contents.append(genai.types.Content(
                role=role,
                parts=[genai.types.Part(text=msg["content"])],
            ))

        response = await self.client.aio.models.generate_content(
            model=kwargs.get("model", self.model),
            contents=contents,
        )
        return response.text or ""

    async def stream(self, messages: list[dict], **kwargs) -> AsyncIterator[str]:
        contents = []
        for msg in messages:
            role = "model" if msg["role"] == "assistant" else "user"
            contents.append(genai.types.Content(
                role=role,
                parts=[genai.types.Part(text=msg["content"])],
            ))

        response = await self.client.aio.models.generate_content_stream(
            model=kwargs.get("model", self.model),
            contents=contents,
        )
        async for chunk in response:
            if chunk.text:
                yield chunk.text
