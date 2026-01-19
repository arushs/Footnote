"""PostHog analytics service for LLM tracing.

Manually tracks Claude API calls with metrics like tokens, latency, and model.
"""

import logging
import time
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

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
    trace_id: str | None = None,
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
        trace_id: Optional trace ID to group multiple generations (e.g., agent iterations)
        properties: Additional custom properties (e.g., mode, conversation_id)
    """
    client = get_posthog_client()
    if client is None:
        logger.warning(
            f"PostHog client not initialized (enabled={settings.posthog_enabled}, "
            f"api_key_set={bool(settings.posthog_api_key)})"
        )
        return

    # PostHog expects latency in seconds
    latency_seconds = latency_ms / 1000.0

    event_properties = {
        "$ai_model": model,
        "$ai_provider": "anthropic",
        "$ai_input_tokens": input_tokens,
        "$ai_output_tokens": output_tokens,
        "$ai_latency": latency_seconds,
    }

    # Add trace_id if provided (enables trace grouping in PostHog)
    if trace_id:
        event_properties["$ai_trace_id"] = trace_id

    if properties:
        event_properties.update(properties)

    client.capture(
        distinct_id=distinct_id,
        event="$ai_generation",
        properties=event_properties,
    )
    logger.info(
        f"PostHog: tracked $ai_generation for {distinct_id} - "
        f"{input_tokens} in / {output_tokens} out tokens, {latency_seconds:.2f}s"
        + (f" (trace: {trace_id[:8]}...)" if trace_id else "")
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


def track_span(
    distinct_id: str,
    trace_id: str,
    span_name: str,
    input_state: dict[str, Any] | None = None,
    output_state: dict[str, Any] | None = None,
    latency_ms: float | None = None,
    is_error: bool = False,
    properties: dict[str, Any] | None = None,
) -> None:
    """
    Track a span event in PostHog for RAG pipeline operations.

    Spans track non-LLM operations like retrieval, reranking, and tool calls.

    Args:
        distinct_id: User ID or "system" for background jobs
        trace_id: Trace ID to group this span with related events
        span_name: Name of the operation (e.g., "hybrid_search", "rerank", "tool_call")
        input_state: Input to the operation (e.g., query, parameters)
        output_state: Output from the operation (e.g., results, scores)
        latency_ms: Operation latency in milliseconds
        is_error: Whether the operation failed
        properties: Additional custom properties
    """
    client = get_posthog_client()
    if client is None:
        return

    event_properties: dict[str, Any] = {
        "$ai_trace_id": trace_id,
        "$ai_span_name": span_name,
        "$ai_is_error": is_error,
    }

    if input_state:
        event_properties["$ai_input_state"] = input_state

    if output_state:
        event_properties["$ai_output_state"] = output_state

    if latency_ms is not None:
        event_properties["$ai_latency"] = latency_ms / 1000.0  # Convert to seconds

    if properties:
        event_properties.update(properties)

    client.capture(
        distinct_id=distinct_id,
        event="$ai_span",
        properties=event_properties,
    )
    logger.info(f"PostHog: tracked $ai_span '{span_name}' (trace: {trace_id[:8]}...)")
