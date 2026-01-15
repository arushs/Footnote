# Refinery Context (footnote)

> **Recovery**: Run `gt prime` after compaction, clear, or new session

Full context is injected by `gt prime` at session start.

## Quick Reference

- Check MQ: `gt mq list`
- Process next: `gt mq process`

## Project Overview

**Refinery** is a full-stack RAG (Retrieval-Augmented Generation) application that enables users to chat with their Google Drive folders using AI-powered search.

## Directory Structure

```
rig/
├── backend/           # Python FastAPI (RAG engine)
│   ├── app/
│   │   ├── models/    # SQLAlchemy ORM (users, folders, files, chunks, conversations)
│   │   ├── routes/    # auth, folders, chat endpoints
│   │   └── services/  # embedding, retrieval, generation, drive API
│   └── main.py
├── frontend/          # React + TypeScript SPA
│   └── src/
│       ├── pages/     # LandingPage, FoldersPage, ChatPage
│       ├── components/# chat, sidebar, sources, ui, overlay
│       ├── hooks/     # useChat, useConversations, useFolderStatus
│       └── contexts/  # AuthContext
├── database/          # PostgreSQL schema with pgvector
└── docker-compose.yml # Multi-container orchestration
```

## Tech Stack

### Backend
- **Framework:** FastAPI (async)
- **ORM:** SQLAlchemy with AsyncPG
- **Database:** PostgreSQL 16 + pgvector extension
- **Package Manager:** uv

### Frontend
- **Framework:** React 18 + TypeScript 5.6
- **Build:** Vite
- **Styling:** Tailwind CSS + Radix UI
- **Testing:** Playwright (E2E), Vitest (unit)

### AI/ML
- **Embeddings:** Together AI (m2-bert-80M, 768-dim)
- **Reranking:** Llama-Rank V1
- **LLM:** Anthropic Claude

### Auth & APIs
- Google OAuth (Drive read-only scope)
- Google Drive API for file access

## RAG Pipeline

1. **Indexing:** Folder → Extract text → Chunk → Embed → Store vectors
2. **Chat:** Query → Embed → Vector search → Rerank → Generate with citations
