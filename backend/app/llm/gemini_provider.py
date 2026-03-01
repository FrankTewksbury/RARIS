import asyncio
import logging
import random
from collections.abc import AsyncIterator

from google import genai
from google.genai import errors, types

from app.config import settings
from app.llm.base import LLMProvider

logger = logging.getLogger(__name__)

# HTTP status codes that are safe to retry
_RETRYABLE_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})

# Subset of retryable codes that also trigger a model downgrade attempt.
# 429 = quota/overload, 503 = service unavailable, 504 = gateway timeout.
_DOWNGRADE_CODES: frozenset[int] = frozenset({429, 503, 504})

_MAX_ATTEMPTS = 4
_BASE_DELAY_S = 1.0
_MAX_DELAY_S = 32.0


def _error_code(exc: Exception) -> int | None:
    """Return HTTP status code from a google.genai exception, or None."""
    code = getattr(exc, "code", None)
    if isinstance(code, int):
        return code
    sc = getattr(exc, "status_code", None)
    if isinstance(sc, int):
        return sc
    return None


def _build_fallback_chain(primary: str) -> list[str]:
    """Return ordered model list: primary first, then configured fallbacks.

    Source order: GEMINI_FALLBACK_MODELS env var (comma-separated), then
    a hardcoded safety net so there is always at least one downgrade option.
    """
    chain = [primary]
    raw = getattr(settings, "gemini_fallback_models", "") or ""
    for m in (m.strip() for m in raw.split(",") if m.strip()):
        if m != primary:
            chain.append(m)
    if len(chain) == 1:
        for m in ("gemini-3.1-pro-preview", "gemini-3.1-pro-preview:no-think", "gemini-3-flash-preview"):
            if m != primary:
                chain.append(m)
    return chain


class GeminiProvider(LLMProvider):
    def __init__(self, model: str | None = None):
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model = model or settings.gemini_model or "gemini-3.1-pro-preview"
        self._fallback_chain = _build_fallback_chain(self.model)

    @staticmethod
    def _build_config(kwargs: dict) -> types.GenerateContentConfig:
        config = types.GenerateContentConfig()
        budget = kwargs.get("thinking_budget", settings.gemini_thinking_budget)
        if budget is not None:
            config.thinking_config = types.ThinkingConfig(thinking_budget=int(budget))
        if "temperature" in kwargs:
            config.temperature = kwargs["temperature"]
        return config

    @staticmethod
    def _build_contents(messages: list[dict]) -> list:
        contents = []
        for msg in messages:
            role = "model" if msg["role"] == "assistant" else "user"
            contents.append(genai.types.Content(
                role=role,
                parts=[genai.types.Part(text=msg["content"])],
            ))
        return contents

    async def _call_with_resilience(
        self,
        contents: list,
        config: types.GenerateContentConfig,
        *,
        label: str = "complete",
    ) -> str:
        """Execute generate_content with bounded exponential backoff and model fallback.

        Retry policy:
        - Retryable codes (429, 500, 502, 503, 504): retry with backoff.
        - Downgrade codes (429, 503, 504): also advance to next model in fallback chain.
        - Non-retryable codes (400, 401, 403, 404): fail fast immediately.
        - Transient transport errors (TimeoutError, ConnectionError, OSError): retry with backoff.
        """
        last_exc: Exception = RuntimeError("No attempts made")
        model_idx = 0
        # region agent log
        import time as _time
        _rlog_path = "/workspace/.cursor/debug-169697.log"
        try:
            import pathlib as _pl
            _pl.Path(_rlog_path).parent.mkdir(parents=True, exist_ok=True)
            with open(_rlog_path, "a") as _f:
                import json as _j
                _f.write(_j.dumps({"sessionId": "169697", "runId": "169697", "hypothesisId": "H3-H4", "location": "gemini_provider.py:_call_with_resilience", "message": "resilience wrapper entered", "data": {"label": label, "fallback_chain": self._fallback_chain, "model": self.model}, "timestamp": int(_time.time() * 1000)}) + "\n")
        except Exception:
            pass
        # endregion

        for attempt in range(_MAX_ATTEMPTS):
            chain_entry = self._fallback_chain[min(model_idx, len(self._fallback_chain) - 1)]
            if chain_entry.endswith(":no-think"):
                current_model = chain_entry.removesuffix(":no-think")
                attempt_config = types.GenerateContentConfig()
                attempt_config.thinking_config = types.ThinkingConfig(thinking_budget=0)
                if config.temperature is not None:
                    attempt_config.temperature = config.temperature
            else:
                current_model = chain_entry
                attempt_config = config
            try:
                response = await self.client.aio.models.generate_content(
                    model=current_model,
                    contents=contents,
                    config=attempt_config,
                )
                if attempt > 0:
                    logger.info(
                        "[gemini] %s recovered attempt=%d model=%s",
                        label, attempt + 1, current_model,
                    )
                return response.text or ""

            except errors.APIError as exc:
                code = _error_code(exc)
                last_exc = exc

                if code not in _RETRYABLE_CODES:
                    logger.error(
                        "[gemini] %s fail-fast code=%s model=%s error=%s",
                        label, code, current_model, exc,
                    )
                    raise

                delay = min(
                    _BASE_DELAY_S * (2 ** attempt) + random.uniform(0.0, 1.0),
                    _MAX_DELAY_S,
                )
                next_model: str | None = None
                if code in _DOWNGRADE_CODES and model_idx < len(self._fallback_chain) - 1:
                    model_idx += 1
                    next_model = self._fallback_chain[model_idx]

                logger.warning(
                    "[gemini] %s retryable attempt=%d/%d code=%s model=%s fallback=%s delay=%.1fs",
                    label, attempt + 1, _MAX_ATTEMPTS, code, current_model,
                    next_model or "same", delay,
                )
                await asyncio.sleep(delay)

            except (TimeoutError, ConnectionError, OSError) as exc:
                last_exc = exc
                delay = min(
                    _BASE_DELAY_S * (2 ** attempt) + random.uniform(0.0, 1.0),
                    _MAX_DELAY_S,
                )
                logger.warning(
                    "[gemini] %s transport-error attempt=%d/%d delay=%.1fs error=%s",
                    label, attempt + 1, _MAX_ATTEMPTS, delay, exc,
                )
                await asyncio.sleep(delay)

        logger.error(
            "[gemini] %s exhausted all %d attempts last_error=%s",
            label, _MAX_ATTEMPTS, last_exc,
        )
        raise last_exc

    async def complete(self, messages: list[dict], **kwargs) -> str:
        contents = self._build_contents(messages)
        config = self._build_config(kwargs)
        return await self._call_with_resilience(contents, config, label="complete")

    async def stream(self, messages: list[dict], **kwargs) -> AsyncIterator[str]:
        # Delegate to the resilient non-streaming path and yield as a single chunk.
        # Streaming with per-chunk retry is not required by the current pipeline.
        contents = self._build_contents(messages)
        config = self._build_config(kwargs)
        text = await self._call_with_resilience(contents, config, label="stream")
        yield text
