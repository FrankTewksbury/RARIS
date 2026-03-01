import logging

from app.config import settings
from app.llm.anthropic_provider import AnthropicProvider
from app.llm.base import LLMProvider
from app.llm.gemini_provider import GeminiProvider
from app.llm.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)

_providers: dict[str, type[LLMProvider]] = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
}


def resolve_provider_name(name: str | None = None) -> str:
    provider_name = (name or settings.llm_provider or "openai").strip().lower()
    if provider_name == "openai" and not settings.openai_api_key and settings.gemini_api_key:
        logger.warning(
            "Requested provider '%s' has no key; falling back to 'gemini'",
            provider_name,
        )
        return "gemini"
    return provider_name


def get_provider(name: str | None = None) -> LLMProvider:
    provider_name = resolve_provider_name(name)
    if provider_name not in _providers:
        raise ValueError(
            f"Unknown LLM provider: {provider_name}. "
            f"Available: {', '.join(_providers.keys())}"
        )
    return _providers[provider_name]()
