from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": "../.env", "extra": "ignore"}

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


settings = Settings()
