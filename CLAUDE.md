# Claude Code Context

## Important Directories

When troubleshooting issues or understanding the codebase, always check:

### `docs/solutions/`
Contains documented solutions to problems that have been solved. Organized by category:
- `database-issues/` - PostgreSQL, migrations, schema problems
- `build-errors/` - Docker, dependency, compilation issues
- `runtime-errors/` - Application crashes, API errors
- `performance-issues/` - Slow queries, optimization fixes

**Always search here first** when encountering an error - the solution may already be documented.

### `docs/guides/`
Contains setup guides and best practices:
- Environment configuration
- Credential management
- Development setup

## Tech Stack

- **Backend**: FastAPI + SQLAlchemy + PostgreSQL (pgvector)
- **Frontend**: React + Vite + TypeScript
- **AI**: Fireworks AI (embeddings), Anthropic Claude (generation), Mistral (PDF OCR)
- **Infrastructure**: Docker Compose

## Common Issues

1. **Database connection errors**: Check `docs/solutions/database-issues/`
2. **Indexing failures**: Check worker logs with `docker-compose logs worker`
3. **Cross-platform dependency issues**: Explicit deps in `pyproject.toml` (e.g., jiter)

## Key Files

- `docker-compose.yml` - Service definitions
- `backend/app/worker.py` - Background indexing worker
- `backend/pyproject.toml` - Python dependencies
- `database/schema.sql` - Database schema
