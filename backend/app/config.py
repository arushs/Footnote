from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://localhost/talk_to_folder"

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"

    # API Keys
    fireworks_api_key: str = ""
    anthropic_api_key: str = ""
    mistral_api_key: str = ""

    # AI Models
    claude_model: str = "claude-opus-4-5-20250514"  # Main generation model
    claude_fast_model: str = "claude-haiku-4-20250514"  # Fast/cheap model for simple tasks

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
