from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://localhost/footnote"

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

    # PostHog LLM Analytics
    posthog_api_key: str = ""
    posthog_host: str = "https://us.i.posthog.com"
    posthog_enabled: bool = True

    # Security
    secret_key: str = "dev-secret-key-change-in-production"
    session_expire_hours: int = 24
    cookie_domain: str | None = (
        None  # Set to ".footnote.one" in production for cross-subdomain cookies
    )

    # Frontend
    frontend_url: str = "http://localhost:3000"
    cors_origins: list[str] = ["http://localhost:3000"]

    # Rate limiting
    rate_limit_enabled: bool = False  # Disabled until slowapi issue is fixed
    rate_limit_chat_per_minute: int = 20
    rate_limit_folder_create_per_hour: int = 10
    rate_limit_folder_sync_per_minute: int = 5
    rate_limit_general_per_minute: int = 100
    rate_limit_status_per_minute: int = 500
    rate_limit_unauthenticated_per_minute: int = 30

    # Request size limits
    max_request_size_bytes: int = 1024 * 1024  # 1MB
    max_chat_message_length: int = 32000  # 32KB
    max_conversation_title_length: int = 255

    # Database pool (API - shorter timeouts for responsive UX)
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30
    db_pool_recycle: int = 1800  # 30 minutes
    db_command_timeout: int = 30
    db_statement_timeout_ms: int = 30000  # 30 seconds

    # Celery database (longer timeouts for batch processing)
    celery_db_pool_size: int = 10
    celery_db_max_overflow: int = 15
    celery_db_pool_recycle: int = 3600  # 1 hour
    celery_db_command_timeout: int = 300  # 5 minutes
    celery_db_statement_timeout_ms: int = 300000  # 5 minutes

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
