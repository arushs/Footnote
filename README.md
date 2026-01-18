# Footnote

Chat with your Google Drive folders using RAG (Retrieval-Augmented Generation).

Footnote indexes your Google Drive documents and lets you have conversations with them. It uses hybrid search (vector + keyword + recency) to find relevant context and Claude to generate responses with citations.

## Key Features

- **Google Drive Integration** - OAuth login, folder picker, automatic sync
- **Multi-format Support** - Google Docs, PDFs (with OCR), images (with vision)
- **Hybrid Search** - Combines semantic similarity, keyword matching, and recency scoring
- **Two Chat Modes**:
  - *Simple RAG* - Fast single-pass retrieval
  - *Agentic RAG* - Iterative tool-use for complex queries
- **Citations** - Responses include clickable references to source documents

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              Frontend                                    │
│                    React + Vite + TypeScript + Tailwind                 │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           Backend (FastAPI)                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │  /api/auth   │  │ /api/folders │  │  /api/chat   │  │ /api/health │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────┐      ┌─────────────┐      ┌─────────────────────────────┐
│ Google APIs │      │   Celery    │      │       Hybrid Search         │
│  (OAuth +   │      │   Worker    │      │  Vector (60%) + Keyword     │
│   Drive)    │      │  Indexing   │      │  (20%) + Recency (20%)      │
└─────────────┘      └─────────────┘      └─────────────────────────────┘
                            │                          │
                            ▼                          ▼
                     ┌─────────────┐           ┌─────────────┐
                     │  Fireworks  │           │   Claude    │
                     │ (Embeddings │           │ (Generation)│
                     │  + Rerank)  │           └─────────────┘
                     └─────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     PostgreSQL + pgvector + Redis                       │
│  users, sessions, folders, files, chunks (768-dim vectors), messages    │
└─────────────────────────────────────────────────────────────────────────┘
```

### Indexing Pipeline

1. User selects a Google Drive folder
2. Celery worker fetches file list and creates indexing jobs
3. For each file:
   - Download/export from Drive
   - Extract text (HTML parsing for Docs, Mistral OCR for PDFs)
   - Split into chunks with heading-aware boundaries
   - Generate embeddings via Fireworks (Nomic 768-dim)
   - Store chunks with vectors and tsvectors for hybrid search

### Retrieval Pipeline

1. Query → Embed with same model
2. Hybrid search: vector similarity + keyword tsvector + recency decay
3. Optional reranking for final top-k
4. Format context → Claude generates response with `[N]` citations
5. Stream response via SSE

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- API keys (see below)

### 1. Clone and configure environment

```bash
git clone <repo>
cd footnote

# Copy environment template
cp .env.example .env
```

### 2. Get API credentials

Edit `.env` with your credentials:

| Variable | Where to get it |
|----------|-----------------|
| `GOOGLE_CLIENT_ID` | [Google Cloud Console](https://console.cloud.google.com/apis/credentials) - Create OAuth 2.0 Client |
| `GOOGLE_CLIENT_SECRET` | Same as above |
| `FIREWORKS_API_KEY` | [Fireworks AI](https://fireworks.ai/) |
| `ANTHROPIC_API_KEY` | [Anthropic Console](https://console.anthropic.com/) |
| `MISTRAL_API_KEY` | [Mistral Console](https://console.mistral.ai/) |
| `SECRET_KEY` | Generate: `python -c "import secrets; print(secrets.token_urlsafe(32))"` |

**Google OAuth Setup:**
1. Create a project in Google Cloud Console
2. Enable Google Drive API and Google Picker API
3. Configure OAuth consent screen (add `../auth/drive.readonly` scope)
4. Create OAuth 2.0 Client ID (Web application)
5. Add `http://localhost:8000/api/auth/google/callback` to authorized redirect URIs

### 3. Start with Docker (recommended)

```bash
# Start all services
docker-compose up

# Frontend: http://localhost:3000
# Backend:  http://localhost:8000
```

## Development

### Running Tests

```bash
# Backend
cd backend && uv run pytest
cd backend && uv run pytest tests/unit/test_hybrid_search.py -v  # single file

# Frontend
cd frontend && npm test
cd frontend && npm run test:e2e  # Playwright
```

### Linting

```bash
# Backend
cd backend && uv run ruff check . && uv run ruff format .

# Frontend
cd frontend && npm run lint
```

### Useful Commands

```bash
# View worker logs
docker-compose logs -f worker

# Reset database
docker-compose down -v && docker-compose up

# Shell into backend container
docker-compose exec backend bash
```

## Deployment

See `render.yaml` for Render deployment configuration. After deploying:

1. Set environment variables in Render dashboard
2. Enable pgvector extension on database:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
3. Update `GOOGLE_REDIRECT_URI` to your production callback URL

## Tech Stack

- **Backend**: FastAPI, SQLAlchemy (async), Celery, Redis
- **Frontend**: React 18, Vite, TypeScript, Tailwind CSS, Radix UI
- **Database**: PostgreSQL 16 with pgvector
- **AI**: Fireworks (Nomic embeddings), Anthropic Claude, Mistral (OCR)
