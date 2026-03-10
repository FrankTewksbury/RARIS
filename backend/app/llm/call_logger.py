"""Structured LLM call logging — Track A observability for Docker + local dev.

Emits structured log lines for every LLM call with Track A fields:
  runId, manifestId, stage, provider, model, errorCode, retryAttempt, fallbackModel

Also provides [STAGE] and [HEARTBEAT] stdout formatters per log-file-rule.mdc §9-10.

Controlled by settings.llm_logging (ON|OFF) and settings.llm_log_prompts (ON|OFF).
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

from app.config import settings

logger = logging.getLogger("app.llm.calls")

# ANSI color constants per log-file-rule.mdc §2
_GREEN = "\033[92m"
_WHITE = "\033[97m"
_YELLOW = "\033[93m"
_RED = "\033[91m"
_PURPLE = "\033[95m"
_RESET = "\033[0m"


def _run_tag(manifest_id: str) -> str:
    """Extract a short run tag from manifest_id for log line prefixes.

    manifest_id format: raris-manifest-{domain}-{YYYYMMDDHHMMSS}
    Returns: RUN-YYYYMMDDHHMMSS, or RUN-UNKNOWN if not parseable.
    """
    if not manifest_id:
        return "RUN-UNKNOWN"
    # Extract trailing timestamp segment (14 digits)
    m = re.search(r"(\d{14})$", manifest_id)
    if m:
        return f"RUN-{m.group(1)}"
    # Fall back to last non-empty segment
    parts = manifest_id.rstrip("-").rsplit("-", 1)
    return f"RUN-{parts[-1]}" if parts else "RUN-UNKNOWN"


@dataclass
class LLMCallRecord:
    """Tracks a single LLM API call for structured logging."""

    provider: str  # gemini | anthropic | openai
    model: str
    method: str  # complete | stream | complete_grounded
    stage: str = ""  # Pipeline stage (e.g. sector_discovery, entity_expansion)
    run_id: str = ""
    manifest_id: str = ""
    prompt_chars: int = 0
    response_chars: int = 0
    duration_ms: float = 0.0
    error_code: int | None = None
    error_message: str = ""
    retry_attempt: int = 0
    fallback_model: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    _start_time: float = field(default=0.0, repr=False)

    def start(self) -> None:
        self._start_time = time.monotonic()

    def finish(self, response_chars: int = 0) -> None:
        self.duration_ms = round((time.monotonic() - self._start_time) * 1000, 1)
        self.response_chars = response_chars


def _is_enabled() -> bool:
    return settings.llm_logging.upper() == "ON"


def _should_log_prompts() -> bool:
    return settings.llm_log_prompts.upper() == "ON"


def log_llm_call_start(record: LLMCallRecord) -> None:
    """Log the start of an LLM call."""
    if not _is_enabled():
        return
    record.start()
    logger.info(
        "[llm-call] START provider=%s model=%s method=%s stage=%s "
        "run_id=%s manifest_id=%s prompt_chars=%d",
        record.provider,
        record.model,
        record.method,
        record.stage,
        record.run_id,
        record.manifest_id,
        record.prompt_chars,
    )


def log_llm_call_success(record: LLMCallRecord) -> None:
    """Log successful completion of an LLM call."""
    if not _is_enabled():
        return
    logger.info(
        "[llm-call] OK provider=%s model=%s method=%s stage=%s "
        "run_id=%s manifest_id=%s response_chars=%d duration_ms=%.1f",
        record.provider,
        record.model,
        record.method,
        record.stage,
        record.run_id,
        record.manifest_id,
        record.response_chars,
        record.duration_ms,
    )


def log_llm_call_error(record: LLMCallRecord) -> None:
    """Log a failed LLM call."""
    if not _is_enabled():
        return
    logger.error(
        "[llm-call] ERROR provider=%s model=%s method=%s stage=%s "
        "run_id=%s manifest_id=%s error_code=%s error=%s "
        "retry_attempt=%d fallback_model=%s duration_ms=%.1f",
        record.provider,
        record.model,
        record.method,
        record.stage,
        record.run_id,
        record.manifest_id,
        record.error_code,
        record.error_message,
        record.retry_attempt,
        record.fallback_model,
        record.duration_ms,
    )


def log_stage(
    stage_name: str,
    *,
    status: str = "running",
    model: str = "",
    sources: int = 0,
    programs: int = 0,
    skipped_batches: int = 0,
    manifest_id: str = "",
) -> None:
    """Emit a [STAGE] summary line to stdout per log-file-rule.mdc §9."""
    if not _is_enabled():
        return
    tag = _run_tag(manifest_id)
    print(
        f"{_GREEN}[{tag}][STAGE]{_RESET} {stage_name} "
        f"status={status} model={model} "
        f"sources={sources} programs={programs} "
        f"skipped_batches={skipped_batches}",
        flush=True,
    )


def log_heartbeat(
    *,
    stage: str,
    batch: str = "",
    items_so_far: int = 0,
    elapsed_s: float = 0.0,
    manifest_id: str = "",
) -> None:
    """Emit a [HEARTBEAT] line to stdout per log-file-rule.mdc §10."""
    if not _is_enabled():
        return
    tag = _run_tag(manifest_id)
    print(
        f"{_YELLOW}[{tag}][HEARTBEAT]{_RESET} stage={stage} "
        f"batch={batch} items_so_far={items_so_far} "
        f"elapsed_s={elapsed_s:.0f}",
        flush=True,
    )


def log_prompt(
    *,
    entity_id: str,
    entity_name: str,
    depth: int,
    prompt_text: str,
    authority_type: str = "",
    jurisdiction_code: str = "",
    manifest_id: str = "",
) -> None:
    """Print the full expansion prompt to stdout when LLM_LOG_PROMPTS=ON.

    Output follows print-header-style.mdc (Major header = GREEN ===, body = WHITE).
    Gated by settings.llm_log_prompts so it is off by default and never pollutes
    production logs unless explicitly enabled.
    """
    if not _should_log_prompts():
        return
    tag = _run_tag(manifest_id)
    header = f"EXPANSION PROMPT  L{depth + 1}  [{entity_id}]"
    bar = "=" * 44
    print(
        f"{_GREEN}{bar}\n"
        f"     [{tag}] {header}\n"
        f"{bar}{_RESET}",
        flush=True,
    )
    print(f"{_WHITE}Entity : {entity_name}{_RESET}", flush=True)
    print(f"{_WHITE}Type   : {authority_type}  |  Jurisdiction: {jurisdiction_code}{_RESET}", flush=True)
    print(f"{_WHITE}{'-' * 60}{_RESET}", flush=True)
    print(f"{_WHITE}{prompt_text}{_RESET}", flush=True)
    print(f"{_GREEN}{bar}{_RESET}\n", flush=True)
