"""
Central configuration module for AI Doc Generator.

Reads settings from environment variables and .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    # Gemini
    gemini_api_key: str = Field(default="", description="Gemini API key")
    gemini_model: str = Field(default="gemini-2.5-flash", description="LLM model name")
    gemini_embedding_model: str = Field(
        default="gemini-embedding-001", description="Embedding model name"
    )

    @field_validator("gemini_api_key", mode="after")
    @classmethod
    def api_key_must_be_set(cls, v: str) -> str:
        """Fail fast if the Gemini API key is missing."""
        if not v or not v.strip():
            raise ValueError(
                "GEMINI_API_KEY is not configured. "
                "Set it in your .env file or export it as an environment variable: "
                "export GEMINI_API_KEY=your_key_here"
            )
        return v.strip()

    # Output
    output_dir: str = Field(default="./docs", description="Output directory for docs")
    temp_dir: str = Field(
        default="/tmp/ai-doc-generator", description="Temp directory for cloned repos"
    )

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")

    # Performance
    max_workers: int = Field(default=4, description="Max parallel workers")
    embedding_cache_file: str = Field(
        default=".embedding_cache.json", description="Embedding cache file path"
    )


# Singleton settings instance
settings = Settings()
