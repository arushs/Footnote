---
title: Conversations Table Missing Columns (title, updated_at)
category: database-issues
component: backend/conversations
symptoms:
  - Cannot chat with uploaded folder
  - 500 error when starting conversation
  - "column 'title' of relation 'conversations' does not exist"
root_cause: Database schema out of sync with model after adding new columns
severity: high
created: 2026-01-15
tags:
  - database
  - schema
  - migrations
  - conversations
---

# Conversations Table Missing Columns

## Problem

After adding `title` and `updated_at` columns to the `Conversation` model, users could not chat with their folders. The chat would fail silently or show errors.

## Symptoms

- Chat fails to start after selecting a folder
- Docker logs show SQLAlchemy errors:
  ```
  sqlalchemy.exc.ProgrammingError: column "title" of relation "conversations" does not exist
  [SQL: INSERT INTO conversations (id, folder_id, title, created_at, updated_at) VALUES ...]
  ```
- Also seen as:
  ```
  ERROR: column conversations.title does not exist at character 51
  ```

## Investigation

1. Checked Docker logs with `docker-compose logs --tail=100`
2. Found PostgreSQL errors about missing columns
3. Compared `Conversation` model in `backend/app/models/db_models.py` with actual database schema
4. Model expected `title` and `updated_at` but database only had `id`, `folder_id`, `created_at`

## Root Cause

The `Conversation` model was updated to include new columns (`title` and `updated_at`) but no database migration was run to add these columns to the existing database. The application has no migration system (like Alembic) configured.

Relevant model code (`backend/app/models/db_models.py:87-94`):
```python
class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    folder_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("folders.id", ondelete="CASCADE"))
    title: Mapped[str | None] = mapped_column(Text, nullable=True)  # NEW
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)  # NEW
```

## Solution

Run ALTER TABLE commands directly on the database to add the missing columns:

```bash
# Find the database name
docker exec footnote-db psql -U postgres -c "\l"
# Database is 'footnote'

# Add the missing columns
docker exec footnote-db psql -U postgres -d footnote -c \
  "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS title TEXT; \
   ALTER TABLE conversations ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();"

# Restart backend to clear any connection state
docker-compose restart backend
```

## Prevention

1. **Set up Alembic migrations**: Configure a proper migration system so schema changes are tracked and applied consistently
2. **Include migration in PRs**: When adding model columns, include the corresponding database migration
3. **Test with fresh database**: After schema changes, test with a fresh database to catch missing migrations early
4. **Document schema changes**: Add notes in commit messages about required database changes

## Related

- Commits adding these columns: `b667eaf Add title and updated_at columns to Conversation model`
- Related conversation-centric API routes: `4752295 Update chat to use conversation-centric API`
