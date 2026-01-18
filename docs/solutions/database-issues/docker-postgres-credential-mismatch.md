---
title: Docker PostgreSQL Authentication Failure Due to Credential Mismatch
category: database-issues
component: backend/database
symptoms:
  - "FATAL: password authentication failed for user 'user'"
  - "Role 'user' does not exist"
  - Frontend proxy errors (ECONNREFUSED) to backend port 8000
  - Docker containers failing to start
root_cause: Credential mismatch between root .env file and docker-compose.yml
severity: high
created: 2026-01-15
tags:
  - docker
  - postgresql
  - authentication
  - credentials
  - environment-configuration
  - docker-compose
---

# Docker PostgreSQL Authentication Failure Due to Credential Mismatch

## Problem

Docker containers fail to start with PostgreSQL authentication errors. The backend cannot connect to the database, causing cascading failures where the frontend proxy cannot reach the backend.

## Symptoms

- Docker logs show authentication errors:
  ```
  footnote-db | FATAL: password authentication failed for user "user"
  footnote-db | DETAIL: Role "user" does not exist.
  ```
- Frontend proxy errors:
  ```
  footnote-frontend | [vite] http proxy error: /api/auth/me
  footnote-frontend | Error: connect ECONNREFUSED 192.168.97.5:8000
  ```
- Backend service fails to start or repeatedly restarts

## Investigation

1. Checked docker-compose logs for error messages
2. Found PostgreSQL rejecting connection for user "user"
3. Examined `docker-compose.yml` - found it uses `postgres:postgres` credentials
4. Examined root `.env` file - found it uses `user:password` credentials
5. Identified the credential mismatch as root cause

## Root Cause

The PostgreSQL container was configured with `postgres:postgres` credentials in `docker-compose.yml`:

```yaml
db:
  environment:
    POSTGRES_USER: postgres
    POSTGRES_PASSWORD: postgres
    POSTGRES_DB: footnote
```

But the root `.env` file had different credentials:

```
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/footnote
```

When the backend tried to connect using the `user` role, PostgreSQL rejected it because only the `postgres` role exists.

## Solution

### Option 1: Update .env to match docker-compose (Recommended)

Edit the root `.env` file to use matching credentials:

**Before:**
```
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/footnote
```

**After:**
```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/footnote
```

Then restart services:
```bash
docker-compose restart backend worker
```

### Option 2: Reset Database Volume

If the database was already initialized with incorrect credentials:

```bash
# Stop all containers and remove volumes
docker-compose down -v

# Restart with correct configuration
docker-compose up
```

This removes the existing database volume and reinitializes with correct credentials.

## Prevention

1. **Use .env.example as template**: Keep a `.env.example` with placeholder values that match docker-compose defaults
2. **Validate credentials on startup**: Add a health check that verifies database connectivity early
3. **Document credential sources**: Add comments in docker-compose.yml indicating where credentials should be defined
4. **Single source of truth**: Consider using docker-compose environment variables that reference the .env file rather than hardcoding credentials in both places

## Credential Alignment Checklist

When setting up or debugging, verify these match:

| Location | User | Password | Host |
|----------|------|----------|------|
| docker-compose.yml `POSTGRES_USER/PASSWORD` | postgres | postgres | - |
| docker-compose.yml `DATABASE_URL` (backend) | postgres | postgres | db |
| docker-compose.yml `DATABASE_URL` (worker) | postgres | postgres | db |
| Root `.env` `DATABASE_URL` | postgres | postgres | localhost |
| `backend/.env` `DATABASE_URL` | postgres | postgres | localhost |

Note: Docker services use `db` as hostname (container name), local development uses `localhost`.

## Related

- Docker Compose configuration: `docker-compose.yml`
- Root environment file: `.env`
- Backend environment file: `backend/.env`
