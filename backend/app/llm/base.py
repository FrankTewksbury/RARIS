from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field


@dataclass
class Citation:
    """A web citation returned by grounded generation."""
    url: str
    title: str = ""


class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, messages: list[dict], **kwargs) -> str:
        """Send messages and return a complete response."""
        ...

    @abstractmethod
    async def stream(self, messages: list[dict], **kwargs) -> AsyncIterator[str]:
        """Send messages and stream response tokens."""
        ...

    async def complete_grounded(
        self, messages: list[dict], **kwargs
    ) -> tuple[str, list[Citation]]:
        """Generate with web search/grounding. Returns (text, citations).

        Default implementation falls back to complete() with no citations.
        Providers override this to add web search capabilities.
        """
        text = await self.complete(messages, **kwargs)
        return text, []
