from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = Field(..., description="OpenAI API key for GPT-4o-mini")
    openai_model: str = Field(default="gpt-4o-mini", description="Chat completion model")
    mcp_server_url: str = Field(
        default="https://order-mcp-74afyau24q-uc.a.run.app/mcp",
        description="MCP Streamable HTTP endpoint",
    )
    agent_max_rounds: int = Field(default=12, ge=1, le=32)
    request_timeout_seconds: float = Field(default=120.0, ge=5.0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
