# feat: Indexing Speed Optimizations

## Overview

Make file indexing significantly faster through batch operations and connection pooling. Pure backend performance improvement with no user-facing changes.

## Problem Statement

**Current Bottlenecks:**
- Sequential chunk inserts: O(n) database round trips per file
- No embedding batch limits: Large documents can timeout API
- New HTTP client per request: Connection overhead on every Drive API call
- Worker concurrency too low: Only 5 concurrent jobs for I/O-bound work

**Impact:**
- Indexing a 50-page PDF takes longer than necessary
- Large folders (100+ files) take minutes instead of seconds
- API timeouts on documents with 100+ chunks

---

## Technical Approach

### Phase 1: Database Optimizations

**1.1 Add composite index for worker queries**

```sql
-- database/migrations/add_indexing_indexes.sql
CREATE INDEX CONCURRENTLY idx_files_folder_status
    ON files(folder_id, index_status);
```

This speeds up the folder progress COUNT query and job claiming.

**1.2 Batch chunk inserts (10-100x faster)**

Replace the sequential loop in `worker.py:224-238` with a single batch insert using `executemany`:

```python
# backend/app/worker.py
async def store_chunks_batch(
    db: AsyncSession,
    file_id: uuid.UUID,
    chunks: list[DocumentChunk],
    embeddings: list[list[float]],
) -> None:
    """Batch insert chunks in a single database operation."""
    if not chunks:
        return

    chunk_values = [
        {
            "id": uuid.uuid4(),
            "file_id": file_id,
            "chunk_text": chunk.text,
            "chunk_embedding": embedding,
            "location": chunk.location,
            "chunk_index": idx,
        }
        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings))
    ]

    # SQLAlchemy 2.0 optimizes this into efficient batch insert
    await db.execute(
        insert(Chunk),
        chunk_values,
    )
```

---

### Phase 2: Embedding Optimizations

**2.1 Batched embeddings with size limits**

Add batch size limits to prevent API timeouts on large documents:

```python
# backend/app/services/embedding.py
import asyncio

MAX_EMBEDDING_BATCH = 50  # Fireworks API optimal batch size
MAX_CONCURRENT_BATCHES = 6  # Stay within rate limits

async def embed_documents_batch(texts: list[str]) -> list[list[float]]:
    """Generate embeddings with parallel batched API calls."""
    if not texts:
        return []

    client = _get_client()

    # Split into optimal-sized batches
    batches = [
        texts[i:i + MAX_EMBEDDING_BATCH]
        for i in range(0, len(texts), MAX_EMBEDDING_BATCH)
    ]

    # Local semaphore (not global - avoids event loop binding issues)
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_BATCHES)

    async def process_batch(batch: list[str]) -> list[list[float]]:
        async with semaphore:
            prefixed = [f"search_document: {t}" for t in batch]
            response = await client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=prefixed,
            )
            return [item.embedding for item in response.data]

    # Process all batches in parallel (limited by semaphore)
    results = await asyncio.gather(
        *[process_batch(b) for b in batches],
        return_exceptions=True,
    )

    # Handle partial failures
    for result in results:
        if isinstance(result, Exception):
            raise result

    return [emb for batch_result in results for emb in batch_result]
```

---

### Phase 3: Network Optimizations

**3.1 Persistent HTTP client for Google Drive API**

Replace per-request clients with a module-level singleton:

```python
# backend/app/services/drive.py
import httpx

_http_client: httpx.AsyncClient | None = None

def _get_http_client() -> httpx.AsyncClient:
    """Get shared HTTP client for connection reuse."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=30.0)
    return _http_client

# Update all methods to use _get_http_client() instead of:
# async with httpx.AsyncClient() as client:
```

---

### Phase 4: Worker Optimizations

**4.1 Increase worker concurrency**

```python
# backend/app/worker.py - Update default concurrency
# Change from 5 to 20 for I/O-bound work
WORKER_CONCURRENCY = int(os.getenv("WORKER_CONCURRENCY", "20"))
```

---

## Acceptance Criteria

### Performance Requirements

- [ ] Batch chunk inserts reduce DB round trips by 90%+ (from O(n) to O(1))
- [ ] Documents with 100+ chunks complete without API timeout
- [ ] Worker concurrency increased from 5 to 20
- [ ] No regression in indexing reliability (error rate stays < 2%)

### Testing Requirements

- [ ] Unit tests for `store_chunks_batch` with various chunk counts
- [ ] Unit tests for `embed_documents_batch` with batch size edge cases
- [ ] Integration test: index 100-chunk document successfully

---

## Files to Modify

| File | Change | Impact |
|------|--------|--------|
| `database/schema.sql` or migration | Add composite index | Faster COUNT queries |
| `backend/app/worker.py:224-238` | Batch chunk inserts | 10-100x faster storage |
| `backend/app/worker.py:378` | Increase concurrency to 20 | 4x throughput |
| `backend/app/services/embedding.py` | Batch limits + parallel | Prevents timeouts |
| `backend/app/services/drive.py` | Connection pooling | 30-50% faster API |

---

## Expected Impact

| Optimization | Individual Improvement |
|--------------|----------------------|
| Batch chunk inserts | 10-100x faster storage |
| Batched embeddings | Prevents API timeouts |
| Connection pooling | 30-50% faster API calls |
| Increased concurrency | 4x throughput |

---

## References

### Internal References
- Current worker: `backend/app/worker.py`
- Embedding service: `backend/app/services/embedding.py`
- Drive service: `backend/app/services/drive.py`
- Database schema: `database/schema.sql`

### External References
- [pgvector bulk loading](https://github.com/pgvector/pgvector#bulk-loading)
- [Fireworks AI rate limits](https://docs.fireworks.ai/guides/rate-limits)
