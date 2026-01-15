"""Mistral AI service using official SDK."""

from collections.abc import AsyncIterator

from mistralai import Mistral

from app.config import settings


DEFAULT_MODEL = "mistral-large-latest"

_client: Mistral | None = None


def get_client() -> Mistral:
    """Get or create the Mistral client."""
    global _client
    if _client is None:
        _client = Mistral(api_key=settings.mistral_api_key)
    return _client


async def generate_stream(
    messages: list[dict],
    model: str = DEFAULT_MODEL,
    max_tokens: int = 4096,
    temperature: float = 0.7,
) -> AsyncIterator[str]:
    """Stream text from Mistral."""
    client = get_client()
    stream = await client.chat.stream_async(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    async for chunk in stream:
        delta = chunk.data.choices[0].delta
        if delta.content:
            yield delta.content


async def generate(
    messages: list[dict],
    model: str = DEFAULT_MODEL,
    max_tokens: int = 4096,
    temperature: float = 0.7,
) -> str:
    """Generate a non-streaming response from Mistral."""
    client = get_client()
    response = await client.chat.complete_async(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return response.choices[0].message.content


async def close_client() -> None:
    """Close the client (no explicit close needed for Mistral)."""
    global _client
    _client = None
