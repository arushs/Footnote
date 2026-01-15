"""Anthropic Claude SDK wrapper service.

Provides a singleton AsyncAnthropic client pattern with streaming
response generation for the RAG pipeline.
"""

from collections.abc import AsyncIterator

from anthropic import AsyncAnthropic

from app.config import settings


# Singleton client instance
_client: AsyncAnthropic | None = None


def get_client() -> AsyncAnthropic:
    """
    Get or create the singleton AsyncAnthropic client.

    Returns:
        The shared AsyncAnthropic client instance.
    """
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


async def generate_stream(
    messages: list[dict],
    system_prompt: str | None = None,
    model: str = "claude-sonnet-4-20250514",
    max_tokens: int = 4096,
) -> AsyncIterator[str]:
    """
    Stream text responses from Claude.

    Args:
        messages: List of message dicts with 'role' and 'content' keys.
        system_prompt: Optional system prompt for context.
        model: Claude model to use.
        max_tokens: Maximum tokens in the response.

    Yields:
        Text chunks from the streaming response.
    """
    client = get_client()
    async with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        messages=messages,
        system=system_prompt or "",
    ) as stream:
        async for text in stream.text_stream:
            yield text


async def close_client() -> None:
    """
    Close the singleton client and release resources.

    Should be called during application shutdown for graceful cleanup.
    """
    global _client
    if _client is not None:
        await _client.close()
        _client = None
