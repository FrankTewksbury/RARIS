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


settings = Settings()
