"""PostHog analytics service for LLM tracing.

Manually tracks Claude API calls with metrics like tokens, latency, and model.
"""

import time
from typing import Any

from app.config import settings

# Singleton PostHog client
_posthog_client = None


def get_posthog_client():
    """
    Get or create the singleton PostHog client.

    Returns:
        The shared PostHog client instance, or None if disabled/not configured.
    """
    global _posthog_client
    if settings.posthog_enabled and settings.posthog_api_key:
        if _posthog_client is None:
            from posthog import Posthog

            _posthog_client = Posthog(
                settings.posthog_api_key,
                host=settings.posthog_host,
            )
        return _posthog_client
    return None


def shutdown_posthog() -> None:
    """
    Shutdown the PostHog client gracefully.

    Should be called during application shutdown.
    """
    global _posthog_client
    if _posthog_client is not None:
        _posthog_client.shutdown()
        _posthog_client = None


def track_llm_generation(
    distinct_id: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: float,
    properties: dict[str, Any] | None = None,
) -> None:
    """
    Track an LLM generation event in PostHog.

    Args:
        distinct_id: User ID or "system" for background jobs
        model: Claude model used (e.g., "claude-sonnet-4-5-20250929")
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        latency_ms: Response latency in milliseconds
        properties: Additional custom properties (e.g., mode, conversation_id)
    """
    client = get_posthog_client()
    if client is None:
        return

    event_properties = {
        "$ai_model": model,
        "$ai_provider": "anthropic",
        "$ai_input_tokens": input_tokens,
        "$ai_output_tokens": output_tokens,
        "$ai_latency": latency_ms,
    }

    if properties:
        event_properties.update(properties)

    client.capture(
        distinct_id=distinct_id,
        event="$ai_generation",
        properties=event_properties,
    )


class LLMTimer:
    """Context manager for timing LLM calls."""

    def __init__(self):
        self.start_time: float = 0
        self.end_time: float = 0

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.end_time = time.perf_counter()

    @property
    def elapsed_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000
