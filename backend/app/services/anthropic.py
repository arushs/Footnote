"""Anthropic Claude service using official SDK."""

from collections.abc import AsyncIterator

from anthropic import AsyncAnthropic

from app.config import settings


DEFAULT_MODEL = "claude-sonnet-4-20250514"

_client: AsyncAnthropic | None = None


def get_client() -> AsyncAnthropic:
    """Get or create the AsyncAnthropic client."""
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


async def generate_stream(
    messages: list[dict],
    system_prompt: str | None = None,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 4096,
    temperature: float = 0.7,
) -> AsyncIterator[str]:
    """Stream text from Claude."""
    client = get_client()
    async with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        messages=messages,
        system=system_prompt or "",
        temperature=temperature,
    ) as stream:
        async for text in stream.text_stream:
            yield text


async def generate(
    messages: list[dict],
    system_prompt: str | None = None,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 4096,
    temperature: float = 0.7,
) -> str:
    """Generate a non-streaming response from Claude."""
    client = get_client()
    response = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=messages,
        system=system_prompt or "",
        temperature=temperature,
    )
    return response.content[0].text


async def close_client() -> None:
    """Close the client connection (call on shutdown)."""
    global _client
    if _client is not None:
        await _client.close()
        _client = None
