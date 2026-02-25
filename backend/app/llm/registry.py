from app.config import settings
from app.llm.anthropic_provider import AnthropicProvider
from app.llm.base import LLMProvider
from app.llm.gemini_provider import GeminiProvider
from app.llm.openai_provider import OpenAIProvider

_providers: dict[str, type[LLMProvider]] = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
}


def get_provider(name: str | None = None) -> LLMProvider:
    provider_name = name or settings.llm_provider
    if provider_name not in _providers:
        raise ValueError(
            f"Unknown LLM provider: {provider_name}. "
            f"Available: {', '.join(_providers.keys())}"
        )
    return _providers[provider_name]()
