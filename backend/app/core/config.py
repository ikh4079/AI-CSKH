from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "AI CSKH Agent"
    app_env: str = "development"
    allowed_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )
    database_url: str = "sqlite:///./agent_logs.db"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    embedding_model: str = "text-embedding-3-small"
    index_dir: str = "data/faiss_index"
    faq_path: str = "data/faq.json"
    memory_window_size: int = 10
    memory_ttl_seconds: int = 1800
    max_llm_retries: int = 4
    request_timeout_seconds: int = 45
    order_id_prefixes: list[str] = Field(default_factory=lambda: ["DH"])
    prompt_injection_patterns: list[str] = Field(
        default_factory=lambda: [
            "ignore previous instructions",
            "bỏ qua hướng dẫn trước",
            "bo qua huong dan truoc",
            "reveal system prompt",
            "tiết lộ system prompt",
            "tiet lo system prompt",
        ]
    )
    discord_webhook_url: str | None = None
    order_source_path: str = "data/orders.json"
    ticket_output_path: str = "data/tickets.json"
    max_agent_steps: int = 6

    @property
    def backend_dir(self) -> Path:
        return Path(__file__).resolve().parents[2]

    def resolve_path(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return self.backend_dir / path


@lru_cache
def get_settings() -> Settings:
    return Settings()
