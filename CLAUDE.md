# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Development Commands

### Backend (Python/FastAPI)
```bash
# Start all services (db, redis, backend, worker, frontend)
docker-compose up

# Run backend tests
cd backend && uv run pytest

# Run a single test
cd backend && uv run pytest tests/unit/test_hybrid_search.py::test_keyword_search -v

# Lint and format
cd backend && uv run ruff check . && uv run ruff format .

# Type check
cd backend && uv run mypy app

# Run database migrations
cd backend && uv run bin/migrate

# Check migration status
cd backend && uv run bin/migrate --status
```

### Frontend (React/Vite)
```bash
# Run dev server
cd frontend && npm run dev

# Run tests
cd frontend && npm test

# Run single test file
cd frontend && npm test -- src/components/chat/ChatMessage.test.tsx

# E2E tests
cd frontend && npm run test:e2e

# Lint
cd frontend && npm run lint
```

## Architecture Overview

### RAG Pipeline

The app indexes Google Drive folders and enables chat with those documents using a two-stage retrieval system:

1. **Indexing** (Celery worker):
   - `app/tasks/indexing.py` - Celery task that processes files
   - Downloads files via Google Drive API → Extracts text (Google Docs via HTML export, PDFs via Mistral OCR) → Chunks with heading-aware splitting → Generates embeddings via Fireworks API → Stores in PostgreSQL with pgvector

2. **Retrieval** (`app/services/hybrid_search.py`):
   - Hybrid search combining: vector similarity (60%), keyword/tsvector (20%), recency decay (20%)
   - Optional reranking via Fireworks for final results

3. **Chat Modes** (`app/services/chat/`):
   - `rag.py` - Simple RAG: single search → format context → stream response
   - `agent.py` - Agentic RAG: Claude tool-use loop with `search_folder`, `get_file_chunks`, `get_file` tools. Iterates up to 10x before synthesizing

### Key Data Flow

```
Google Drive → DriveService → ExtractionService → chunk_document() → embed_documents_batch()
                                                                              ↓
User Query → hybrid_search() → rerank() → Claude API → SSE streaming response
```

### Database Schema

- `users`, `sessions` - Google OAuth
- `folders` - Indexed folders with sync state
- `files` - File metadata, preview, file-level embedding
- `chunks` - Text chunks with embeddings (768-dim Nomic) and tsvector for hybrid search
- `conversations`, `messages` - Chat history with citations stored as JSONB

## Important Directories

### `docs/solutions/`
**Check here first** when encountering errors. Contains documented solutions organized by category:
- `database-issues/` - PostgreSQL, migrations, schema problems
- `build-errors/` - Docker, dependency issues
- `runtime-errors/` - Application crashes, API errors

### Key Files
- `backend/app/config.py` - All environment variables and settings
- `backend/app/services/file/embedding.py` - Fireworks API for embeddings
- `backend/app/celery_app.py` - Celery configuration
- `database/schema.sql` - Full database schema with indexes

## Tech Stack

- **Backend**: FastAPI + SQLAlchemy (async) + PostgreSQL (pgvector)
- **Frontend**: React 18 + Vite + TypeScript + Tailwind + Radix UI
- **Task Queue**: Celery with Redis broker
- **AI**: Fireworks (Nomic embeddings), Anthropic Claude (generation), Mistral (PDF OCR)
- **Deployment**: Docker Compose (dev), Render (prod via `render.yaml`)
