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

    # RAG retrieval quality thresholds
    confidence_threshold: float = 0.6
    min_result_count: int = 3
    max_retrieval_attempts: int = 3
    max_context_documents: int = 20
    multi_query_count: int = 3

    # Tool execution settings (003)
    tool_rate_limit_per_minute: int = 10
    tool_dollar_cap: float = 100.0
    approval_timeout_seconds: int = 300
    tool_execution_enabled: bool = True


settings = Settings()
