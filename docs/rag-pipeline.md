# RAG Pipeline Architecture

This document explains how the RAG (Retrieval-Augmented Generation) pipeline works, specifically focusing on the two types of embeddings and the hybrid retrieval system.

## 1. Indexing Pipeline (Two Types of Embeddings)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           INDEXING PIPELINE                                  │
└─────────────────────────────────────────────────────────────────────────────┘

   Google Drive File
          │
          ▼
   ┌──────────────┐
   │ Download &   │
   │ Extract Text │  (Google Docs → HTML export, PDFs → Mistral OCR)
   └──────────────┘
          │
          ▼
   ┌──────────────────────────────────────────────────────────────────────┐
   │                    GENERATE FILE PREVIEW                              │
   │         (first 500 chars + headings = document summary)               │
   └──────────────────────────────────────────────────────────────────────┘
          │
          ├─────────────────────────────────────┐
          │                                     │
          ▼                                     ▼
   ┌─────────────────────┐              ┌─────────────────────┐
   │  FILE-LEVEL EMBED   │              │   CHUNK DOCUMENT    │
   │  ━━━━━━━━━━━━━━━━━  │              │   ━━━━━━━━━━━━━━━   │
   │  "search_document:  │              │  Semantic-aware     │
   │   {preview}"        │              │  splitting:         │
   │                     │              │  • 1500 char target │
   │  → 768-dim vector   │              │  • 150 char overlap │
   │  → Stored on file   │              │  • Heading context  │
   └─────────────────────┘              └─────────────────────┘
                                                │
                                                ▼
                              ┌───────────────────────────────────┐
                              │  CONTEXTUAL_CHUNKING_ENABLED?     │
                              └───────────────────────────────────┘
                                      │               │
                                     YES              NO
                                      │               │
                                      ▼               │
                    ┌─────────────────────────────┐   │
                    │  CONTEXT-AWARE EMBEDDING    │   │
                    │  ━━━━━━━━━━━━━━━━━━━━━━━━   │   │
                    │                             │   │
                    │  For each chunk, call       │   │
                    │  Claude Haiku with:         │   │
                    │                             │   │
                    │  ┌───────────────────────┐  │   │
                    │  │ Document: {filename}  │  │   │
                    │  │                       │  │   │
                    │  │ {first 6000 chars}    │  │   │
                    │  │ ---                   │  │   │
                    │  │ Chunk to contextualize│  │   │
                    │  │ {chunk_text}          │  │   │
                    │  │                       │  │   │
                    │  │ → "1-2 sentences      │  │   │
                    │  │    situating chunk"   │  │   │
                    │  └───────────────────────┘  │   │
                    │                             │   │
                    │  Result:                    │   │
                    │  "{context}\n\n{chunk}"     │   │
                    └─────────────────────────────┘   │
                                      │               │
                                      ▼               ▼
                              ┌───────────────────────────────────┐
                              │        CHUNK-LEVEL EMBED          │
                              │        ━━━━━━━━━━━━━━━━━━         │
                              │   "search_document: {chunk_text}" │
                              │                                   │
                              │   → Batch embed via Fireworks     │
                              │   → 768-dim Nomic vectors         │
                              │   → Store with tsvector           │
                              └───────────────────────────────────┘
                                              │
                                              ▼
                              ┌───────────────────────────────────┐
                              │     PostgreSQL + pgvector          │
                              │   ┌─────────┬──────────┬────────┐ │
                              │   │ text    │ embedding│tsvector│ │
                              │   │ heading │ (768-dim)│ (FTS)  │ │
                              │   └─────────┴──────────┴────────┘ │
                              └───────────────────────────────────┘
```

### Embedding Types Explained

| Type | Source | Purpose | Storage |
|------|--------|---------|---------|
| **File-level** | First 500 chars + headings | Document-level retrieval, organization | `files.embedding` |
| **Chunk-level** | Individual text chunks | Fine-grained semantic search | `chunks.embedding` |

---

## 2. Retrieval Pipeline (Hybrid Search)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           RETRIEVAL PIPELINE                                 │
└─────────────────────────────────────────────────────────────────────────────┘

   User Query: "How does authentication work?"
          │
          ▼
   ┌──────────────────────────────────────────────────────────────────────┐
   │                      EMBED QUERY                                      │
   │              "search_query: {user_query}"                             │
   │                   → 768-dim vector                                    │
   └──────────────────────────────────────────────────────────────────────┘
          │
          ▼
   ┌──────────────────────────────────────────────────────────────────────┐
   │                      HYBRID SEARCH                                    │
   │   Combines 3 signals with weighted scoring                            │
   └──────────────────────────────────────────────────────────────────────┘
          │
          ├──────────────────┬──────────────────┬──────────────────┐
          │                  │                  │                  │
          ▼                  ▼                  ▼                  │
   ┌────────────┐     ┌────────────┐     ┌────────────┐            │
   │  VECTOR    │     │  KEYWORD   │     │  RECENCY   │            │
   │  ━━━━━━━   │     │  ━━━━━━━   │     │  ━━━━━━━   │            │
   │  60%       │     │  20%       │     │  20%       │            │
   │            │     │            │     │            │            │
   │ Cosine     │     │ PostgreSQL │     │ Exponential│            │
   │ similarity │     │ tsvector   │     │ decay      │            │
   │ via <=>    │     │ full-text  │     │            │            │
   │            │     │ search     │     │ half-life  │            │
   │            │     │            │     │ = 30 days  │            │
   └────────────┘     └────────────┘     └────────────┘            │
          │                  │                  │                  │
          └──────────────────┴──────────────────┘                  │
                             │                                     │
                             ▼                                     │
   ┌──────────────────────────────────────────────────────────────────┐
   │                 WEIGHTED SCORE                                    │
   │                                                                   │
   │  score = (0.6 × vector) + (0.2 × keyword) + (0.2 × recency)       │
   │                                                                   │
   │  → Returns top 30 candidates                                      │
   └──────────────────────────────────────────────────────────────────┘
                             │
                             ▼
   ┌──────────────────────────────────────────────────────────────────┐
   │              OPTIONAL: RERANK                                     │
   │                                                                   │
   │  Qwen3 reranker (Fireworks API)                                   │
   │  → Reorder top 30 → Return final top 10                           │
   └──────────────────────────────────────────────────────────────────┘
                             │
                             ▼
   ┌──────────────────────────────────────────────────────────────────┐
   │              RETRIEVED CHUNKS                                     │
   │                                                                   │
   │  [                                                                │
   │    { text, score, file_name, heading_context, ... },              │
   │    { text, score, file_name, heading_context, ... },              │
   │    ...                                                            │
   │  ]                                                                │
   └──────────────────────────────────────────────────────────────────┘
                             │
                             ▼
                    Claude API for response generation
```

### Hybrid Search Weights

| Signal | Weight | Description |
|--------|--------|-------------|
| **Vector** | 60% | Semantic similarity via cosine distance |
| **Keyword** | 20% | PostgreSQL full-text search (tsvector) |
| **Recency** | 20% | Exponential decay favoring recent files |

---

## 3. Context-Aware Embedding (Deep Dive)

The "context-aware" embedding works by **prepending situational context** before embedding each chunk:

### Without Context (default)

```
Chunk: "The function returns a JWT token after validation."

Embedded as: "search_document: The function returns a JWT..."
```

### With Context (`CONTEXTUAL_CHUNKING_ENABLED=true`)

```
Claude generates: "This section describes the token generation
                   step in the OAuth flow."

Embedded as: "search_document: This section describes the token
              generation step in the OAuth flow.

              The function returns a JWT token after..."
```

### Why This Helps

The context helps the embedding capture **what the chunk is about** in the document's larger context, improving retrieval accuracy for ambiguous queries.

For example, a chunk saying "returns a token" could be about:
- Authentication tokens
- API rate limiting tokens
- Session tokens
- Payment tokens

With context, the embedding knows it's specifically about "OAuth token generation", making it more likely to match relevant queries.

---

## 4. Key Code Locations

| Component | File | Key Lines |
|-----------|------|-----------|
| File-level embedding | `backend/app/tasks/indexing.py` | 289 |
| Chunk-level embedding | `backend/app/tasks/indexing.py` | 311-312 |
| Context generation | `backend/app/tasks/indexing.py` | 86-117 |
| Hybrid search | `backend/app/services/hybrid_search.py` | 107-134 |
| Vector search | `backend/app/services/hybrid_search.py` | 190-247 |
| Keyword search | `backend/app/services/hybrid_search.py` | 137-187 |
| Recency scoring | `backend/app/services/hybrid_search.py` | 75-104 |
| Reranking | `backend/app/services/hybrid_search.py` | 360-417 |

---

## 5. Configuration

Enable context-aware embeddings by setting:

```bash
CONTEXTUAL_CHUNKING_ENABLED=true
```

This is disabled by default (`config.py:37`) because it adds latency and API costs (one Claude Haiku call per chunk).
