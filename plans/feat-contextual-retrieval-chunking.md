# Feature: Contextual Retrieval for Improved RAG

## Overview

Implement Anthropic's **Contextual Retrieval** technique to improve retrieval accuracy by prepending context to each chunk before embedding. Research shows this reduces retrieval failures by **35-67%**.

---

## Problem Statement

Traditional chunking loses context:

**Before:** `"The company's revenue grew by 3% over the previous quarter."`
*Which company? Which quarter?*

**After:** `"From ACME Corp's Q2 2023 SEC filing. The company's revenue grew by 3% over the previous quarter."`

---

## Technical Approach

### Architecture (Minimal Change)

```
Current:  Extract → Chunk → Embed chunks → Store
New:      Extract → Chunk → Add context → Embed contextualized chunks → Store
                              ↑
                         Claude Haiku (parallel, with retry)
```

### Design Decisions (Post-Review)

| Decision | Rationale |
|----------|-----------|
| **No schema changes** | Context is only needed at embedding time. Just prepend before embedding. |
| **No feature flag for v1** | Ship it. Add flag later if needed (5 min change). |
| **Parallel LLM calls** | Sequential calls = 50x slower. Use `asyncio.gather` + semaphore. |
| **Retry with backoff** | Rate limits are expected. Use tenacity for automatic retry. |
| **Single file change** | All logic in `worker.py`. No new modules. |

### Key File to Modify

| File | Changes |
|------|---------|
| `backend/app/worker.py` | Add `_generate_chunk_contexts()` function, call before embedding |

---

## Implementation

### Complete Implementation (~40 lines)

**File:** `backend/app/worker.py`

```python
# Add imports at top
import asyncio
from tenacity import retry, retry_if_exception_type, wait_exponential, stop_after_attempt

# Add after existing imports
CONTEXT_PROMPT = """Document: {file_name}

{document_excerpt}

---
Chunk to contextualize:
{chunk_text}

Write 1-2 sentences situating this chunk within the document. Output only the context."""


@retry(
    retry=retry_if_exception_type(Exception),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(3),
    reraise=False,
)
async def _generate_single_context(
    client,
    file_name: str,
    document_excerpt: str,
    chunk_text: str,
) -> str | None:
    """Generate context for a single chunk with retry."""
    try:
        response = await client.messages.create(
            model=settings.claude_fast_model,
            max_tokens=100,
            temperature=0.0,
            messages=[{
                "role": "user",
                "content": CONTEXT_PROMPT.format(
                    file_name=file_name,
                    document_excerpt=document_excerpt,
                    chunk_text=chunk_text,
                )
            }]
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.warning(f"Context generation failed: {e}")
        return None


async def _generate_chunk_contexts(
    file_name: str,
    full_document: str,
    chunks: list,
    max_concurrent: int = 5,
) -> list[str]:
    """Generate contexts for all chunks in parallel with bounded concurrency."""
    # Skip for very short documents
    if len(full_document) < 500:
        return [chunk.text for chunk in chunks]

    # Get document excerpt centered approach would be better,
    # but start simple with first 6000 chars
    doc_excerpt = full_document[:6000]
    if len(full_document) > 6000:
        doc_excerpt += "\n[...truncated...]"

    client = get_anthropic_client()
    semaphore = asyncio.Semaphore(max_concurrent)

    async def generate_with_limit(chunk):
        async with semaphore:
            ctx = await _generate_single_context(
                client, file_name, doc_excerpt, chunk.text
            )
            if ctx:
                return f"{ctx}\n\n{chunk.text}"
            return chunk.text

    return await asyncio.gather(*[generate_with_limit(c) for c in chunks])
```

### Worker Integration

**File:** `backend/app/worker.py` (modify `process_job` around line 195)

```python
# Replace lines 195-197 with:

# Generate contextualized chunk texts (parallel with retry)
full_document = "\n\n".join(b.text for b in document.blocks)
chunk_texts = await _generate_chunk_contexts(
    file_name=file.file_name,
    full_document=full_document,
    chunks=chunks,
)

# Embed the contextualized texts
chunk_embeddings = await embed_documents_batch(chunk_texts)

# Store original chunk text (not contextualized) for display
chunk_values = [
    {
        "id": str(uuid.uuid4()),
        "file_id": str(job.file_id),
        "chunk_text": chunk.text,  # Original for display/keyword search
        "chunk_embedding": format_vector(embedding),
        "location": json.dumps(chunk.location),
        "chunk_index": idx,
    }
    for idx, (chunk, embedding) in enumerate(zip(chunks, chunk_embeddings))
]
```

---

## Acceptance Criteria

- [ ] Context generated for each chunk using Claude Haiku (parallel)
- [ ] Contextualized text embedded, original text stored for display
- [ ] Rate limits handled with exponential backoff (3 retries)
- [ ] Short documents (<500 chars) skip context generation
- [ ] Failures fall back gracefully (use original chunk text)
- [ ] No schema changes required
- [ ] No breaking changes to search API

---

## Edge Cases

| Scenario | Handling |
|----------|----------|
| Rate limit (429) | Retry 3x with exponential backoff (2s, 4s, 8s) |
| API error | Log warning, use original chunk text |
| Short document (<500 chars) | Skip context generation entirely |
| Long document | Truncate to first 6000 chars with "[...truncated...]" |

---

## Testing

**File:** `backend/tests/unit/test_contextual_retrieval.py`

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_generate_chunk_contexts_success():
    """Test successful parallel context generation."""
    with patch("app.worker.get_anthropic_client") as mock_client:
        mock_response = AsyncMock()
        mock_response.content = [AsyncMock(text="From the intro section.")]
        mock_client.return_value.messages.create = AsyncMock(return_value=mock_response)

        from app.worker import _generate_chunk_contexts
        from app.services.chunking import DocumentChunk

        chunks = [DocumentChunk(text="Test chunk", location={}, chunk_index=0)]
        results = await _generate_chunk_contexts("test.pdf", "A" * 600, chunks)

        assert len(results) == 1
        assert "From the intro section." in results[0]
        assert "Test chunk" in results[0]

@pytest.mark.asyncio
async def test_short_document_skips_context():
    """Test that short documents skip context generation."""
    from app.worker import _generate_chunk_contexts
    from app.services.chunking import DocumentChunk

    chunks = [DocumentChunk(text="Short", location={}, chunk_index=0)]
    results = await _generate_chunk_contexts("test.pdf", "Short doc", chunks)

    assert results == ["Short"]  # No context added

@pytest.mark.asyncio
async def test_api_failure_falls_back():
    """Test graceful fallback on API failure."""
    with patch("app.worker.get_anthropic_client") as mock_client:
        mock_client.return_value.messages.create = AsyncMock(
            side_effect=Exception("API error")
        )

        from app.worker import _generate_chunk_contexts
        from app.services.chunking import DocumentChunk

        chunks = [DocumentChunk(text="Original text", location={}, chunk_index=0)]
        results = await _generate_chunk_contexts("test.pdf", "A" * 600, chunks)

        assert results == ["Original text"]  # Falls back to original
```

---

## Cost Analysis

| Metric | Value |
|--------|-------|
| Per chunk | ~$0.00004 (Haiku) |
| Per file (10 chunks avg) | ~$0.0004 |
| Per 1000 files | ~$0.40 |

---

## What We're NOT Doing (YAGNI)

| Removed | Why |
|---------|-----|
| `chunk_context` column | Not needed - context only used at embed time |
| `indexing_version` column | No re-indexing feature planned |
| Feature flag | Just ship it. Add in 5 min if needed. |
| Separate config file changes | No config needed |
| Database migration | No schema changes |
| 5-phase rollout | Overkill for internal tool |

---

## Files to Modify

| File | Changes | LOC |
|------|---------|-----|
| `backend/app/worker.py` | Add context generation functions | ~40 |
| `backend/tests/unit/test_contextual_retrieval.py` | New test file | ~50 |

**Total: ~90 lines of code, 1 production file changed**

---

## References

- [Anthropic - Introducing Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval)
- [Anthropic Cookbook - Contextual Embeddings](https://github.com/anthropics/anthropic-cookbook/blob/main/capabilities/contextual-embeddings/guide.ipynb)
