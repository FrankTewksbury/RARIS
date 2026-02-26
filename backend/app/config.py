import logging

from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = {"env_file": "../.env", "extra": "ignore"}

    # Environment
    environment: str = "development"  # development | staging | production

    # Database
    database_url: str = "postgresql+asyncpg://raris:changeme@localhost:5432/raris"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # LLM
    llm_provider: str = "openai"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""

    # Embeddings
    embedding_model: str = "text-embedding-3-large"
    embedding_dimensions: int = 3072

    # Retrieval
    rerank_method: str = "llm"  # llm | none
    search_top_k: int = 20
    rrf_k: int = 60

    # Ingestion
    chunk_min_tokens: int = 500
    chunk_max_tokens: int = 1000
    chunk_overlap_tokens: int = 50

    # Rate limiting
    rate_limit_rpm: int = 60  # Requests per minute (0 = disabled)

    # Auth
    auth_enabled: bool = False  # Set True to require API keys

    # Scheduler
    scheduler_enabled: bool = False  # Set True to enable background jobs
    monitor_schedule_hour: int = 2  # Hour (UTC) for change monitor
    snapshot_schedule_hour: int = 3  # Hour (UTC) for accuracy snapshot

    # Logging
    log_level: str = "INFO"

    def validate_on_startup(self) -> None:
        """Log warnings for missing or misconfigured settings."""
        provider_key_map = {
            "openai": self.openai_api_key,
            "anthropic": self.anthropic_api_key,
            "gemini": self.gemini_api_key,
        }
        active_key = provider_key_map.get(self.llm_provider, "")
        if not active_key:
            logger.warning(
                "LLM provider '%s' selected but no API key set — "
                "LLM-dependent features will fail",
                self.llm_provider,
            )

        if self.environment == "production" and not self.auth_enabled:
            logger.warning("Running in production with auth DISABLED")

        if self.database_url.endswith("changeme"):
            logger.warning("Using default database password — change for production")

        logger.info(
            "Config: env=%s auth=%s scheduler=%s llm=%s",
            self.environment,
            self.auth_enabled,
            self.scheduler_enabled,
            self.llm_provider,
        )


settings = Settings()
