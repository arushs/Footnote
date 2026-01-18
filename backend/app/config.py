from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://localhost/talk_to_folder"

    @field_validator("database_url", mode="before")
    @classmethod
    def convert_database_url(cls, v: str) -> str:
        """Convert Render's postgres:// URL to asyncpg format."""
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        if v.startswith("postgresql://") and "+asyncpg" not in v:
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    # Redis (Celery broker)
    redis_url: str = "redis://localhost:6379/0"

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"

    # API Keys
    fireworks_api_key: str = ""
    anthropic_api_key: str = ""
    mistral_api_key: str = ""

    # AI Models
    claude_model: str = "claude-sonnet-4-5-20250929"  # Main generation model
    claude_fast_model: str = "claude-haiku-4-5-20251001"  # Fast/cheap model for simple tasks

    # Indexing
    contextual_chunking_enabled: bool = False  # Add context to chunks via LLM (increases API usage)

    # Security
    secret_key: str = "dev-secret-key-change-in-production"
    session_expire_hours: int = 24

    # Frontend
    frontend_url: str = "http://localhost:3000"
    cors_origins: list[str] = ["http://localhost:3000"]

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
