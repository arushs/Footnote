"""Rate limiting middleware using SlowAPI with Redis backend."""

import logging

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings

logger = logging.getLogger(__name__)


def get_user_key(request: Request) -> str:
    """Extract user identifier for rate limiting.

    Uses session user_id if authenticated, otherwise falls back to IP address.
    This ensures rate limits are per-user for authenticated requests and
    per-IP for unauthenticated requests.
    """
    # Check if user_id was set by auth middleware/dependency
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"

    # Fallback to IP-based limiting
    return f"ip:{get_remote_address(request)}"


def get_ip_key(request: Request) -> str:
    """Always use IP address for rate limiting (for unauthenticated endpoints)."""
    return f"ip:{get_remote_address(request)}"


# Initialize limiter with Redis backend for distributed rate limiting
# Uses the same Redis as Celery broker
limiter = Limiter(
    key_func=get_user_key,
    storage_uri=settings.redis_url,
    default_limits=[f"{settings.rate_limit_general_per_minute}/minute"],
    headers_enabled=True,  # Include X-RateLimit-* headers in responses
    enabled=settings.rate_limit_enabled,
)


def rate_limit_chat():
    """Decorator for chat endpoint rate limit."""
    return limiter.limit(f"{settings.rate_limit_chat_per_minute}/minute")


def rate_limit_folder_create():
    """Decorator for folder creation rate limit."""
    return limiter.limit(f"{settings.rate_limit_folder_create_per_hour}/hour")


def rate_limit_folder_sync():
    """Decorator for folder sync rate limit."""
    return limiter.limit(f"{settings.rate_limit_folder_sync_per_minute}/minute")


def rate_limit_status():
    """Decorator for status polling endpoints (higher limit)."""
    return limiter.limit(f"{settings.rate_limit_status_per_minute}/minute")


def rate_limit_unauthenticated():
    """Decorator for unauthenticated endpoints (IP-based)."""
    return limiter.limit(
        f"{settings.rate_limit_unauthenticated_per_minute}/minute", key_func=get_ip_key
    )
