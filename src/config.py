from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = ""
    database_url: str = (
        "postgresql+psycopg://agentic_rag:agentic_rag_dev@localhost:5432/agentic_rag"
    )
    llm_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    log_level: str = "INFO"


settings = Settings()
