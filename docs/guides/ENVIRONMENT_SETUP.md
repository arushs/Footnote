# Environment Setup Guide

This guide explains how to properly configure credentials for different environments and avoid the database credential mismatch issue.

## Quick Start

### Local Development
```bash
# 1. Copy the example file
cp .env.example .env

# 2. Edit .env and add your API keys
# DATABASE_URL should use: localhost
# DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/footnote

# 3. Start your local services
npm run dev
# or
python -m uvicorn main:app --reload
```

### Docker Development
```bash
# 1. Ensure .env exists with your API keys
cp .env.example .env
# Edit .env and add your credentials

# 2. Validate configuration
./scripts/validate-credentials.sh docker

# 3. Start all services
docker-compose up
```

---

## The Credential Mismatch Issue

### What Happened

The root cause was using different DATABASE_URL values:

- **Root `.env` file**: `postgresql+asyncpg://postgres:postgres@localhost:5432/footnote`
- **Docker container environment**: `postgresql+asyncpg://postgres:postgres@db:5432/footnote`

Inside Docker containers, `localhost` refers to the container itself, not the host machine. To connect to another container, you must use the Docker service name (e.g., `db`).

### Why This Matters

| Context | Database Hostname | Why |
|---------|-------------------|-----|
| **Local Dev** | `localhost` | Direct connection to PostgreSQL running on your machine |
| **Docker Container** | `db` | Uses Docker service name for inter-container communication |
| **Production** | `your-db.rds.amazonaws.com` | Uses actual database endpoint |

---

## Environment-Specific Configuration

### 1. Local Development (localhost)

**When to use**: Running services directly on your machine without Docker

```env
# .env (for local development)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/footnote
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
# ... other credentials
```

**How to start:**
```bash
# Terminal 1: Start PostgreSQL (if not running as service)
docker run --name postgres -e POSTGRES_PASSWORD=postgres -d -p 5432:5432 postgres:16

# Terminal 2: Start backend
cd backend
python -m uvicorn main:app --reload

# Terminal 3: Start frontend
cd frontend
npm run dev
```

### 2. Docker Containers (service names)

**When to use**: Using `docker-compose up` to run all services together

```env
# .env (for docker-compose)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/footnote
# ↑ Note: 'db' is the service name in docker-compose.yml
```

**How to start:**
```bash
./scripts/validate-credentials.sh docker
docker-compose up
```

**docker-compose.yml configuration:**
```yaml
services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: footnote

  backend:
    environment:
      # Option 1: Use value from .env file
      DATABASE_URL: postgresql+asyncpg://postgres:postgres@db:5432/footnote

      # Option 2: Reference from .env file
      # DATABASE_URL: ${DATABASE_URL}

  # Use env_file to load credentials
  env_file:
    - .env.docker  # Database URL for Docker
    - .env         # API keys and other values
```

### 3. Production (managed database)

**When to use**: Deploying to AWS, GCP, Heroku, etc.

```env
# .env.production (DO NOT commit to git)
DATABASE_URL=postgresql+asyncpg://produser:prodpass123@your-prod-db.rds.amazonaws.com:5432/production_db

# API keys
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
ANTHROPIC_API_KEY=...
# ... etc
```

**Better approach: Use secrets management**

Instead of storing credentials in `.env` files:
- AWS: Use AWS Secrets Manager or Parameter Store
- GCP: Use Secret Manager
- Heroku: Use Config Vars
- Docker/Kubernetes: Use Docker Secrets or Kubernetes Secrets

```yaml
# Example: Kubernetes deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: footnote-backend
spec:
  template:
    spec:
      containers:
      - name: backend
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: app-secrets
              key: database-url
        - name: ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: app-secrets
              key: anthropic-api-key
```

---

## Validation & Verification

### Validate Your Setup

Before starting services, always validate:

```bash
# For local development
./scripts/validate-credentials.sh local

# For Docker
./scripts/validate-credentials.sh docker

# For production
./scripts/validate-credentials.sh production
```

### Debug Configuration Issues

If services won't start, use the debug script:

```bash
# Shows current configuration (sanitized)
./scripts/debug-config.sh

# Check database connectivity
psql -h localhost -U postgres -d footnote -c "SELECT 1"

# Check Docker service connectivity (from inside container)
docker-compose exec backend psql -h db -U postgres -d footnote -c "SELECT 1"

# View logs
docker-compose logs backend
docker-compose logs db
```

### Test Configuration Manually

```bash
# Test local database connection
psql postgresql://postgres:postgres@localhost:5432/footnote

# Test from Python
from sqlalchemy import create_engine
engine = create_engine("postgresql://postgres:postgres@localhost:5432/footnote")
with engine.connect() as conn:
    result = conn.execute("SELECT 1")
    print(result.fetchone())

# Test from Docker container
docker-compose exec backend python -c "
from sqlalchemy import create_engine
engine = create_engine('postgresql://postgres:postgres@db:5432/footnote')
with engine.connect() as conn:
    print(conn.execute('SELECT 1').fetchone())
"
```

---

## Files to Manage

### Files to Commit to Git
```
.env.example              # Template for credentials
.env.docker               # Docker-specific config template
.gitignore               # Include .env patterns
CREDENTIAL_MANAGEMENT.md # This documentation
ENVIRONMENT_SETUP.md     # This file
scripts/validate-credentials.sh
scripts/debug-config.sh
```

### Files to Add to .gitignore
```
# Local environment variables (NEVER commit actual credentials)
.env
.env.local
.env.*.local

# Backend environments
backend/.env
backend/.env.local

# Frontend environments
frontend/.env
frontend/.env.local

# Sensitive files
*.key
*.pem
credentials.json
secrets.json
```

### Update Your .gitignore
```bash
cat >> .gitignore << 'EOF'

# Environment variables - NEVER commit actual credentials
.env
.env.local
.env.*.local
backend/.env
backend/.env.local
frontend/.env
frontend/.env.local

# Sensitive files
*.key
*.pem
credentials.json
secrets.json
EOF
```

---

## Troubleshooting

### "permission denied" when connecting to database

**Problem**: `psql: could not connect to server: Connection refused`

**Solution**:
```bash
# Local: Make sure PostgreSQL is running
brew services start postgresql@15

# Docker: Make sure the db service is running
docker-compose logs db
docker-compose exec db pg_isready -U postgres

# Check the hostname being used
grep DATABASE_URL .env
```

### "Docker authentication failed"

**Problem**: Backend container can't connect to database

**Solution**:
```bash
# Check DATABASE_URL uses 'db' not 'localhost'
grep DATABASE_URL .env

# Should be: postgresql+asyncpg://postgres:postgres@db:5432/...
# NOT:       postgresql+asyncpg://postgres:postgres@localhost:5432/...

# Run validation
./scripts/validate-credentials.sh docker

# Check database credentials match docker-compose.yml
```

### "Invalid credentials"

**Problem**: PostgreSQL says credentials don't match

**Solution**:
```bash
# Verify credentials in both places match:

# 1. Root .env
grep POSTGRES_USER .env
grep POSTGRES_PASSWORD .env

# 2. docker-compose.yml
grep -A 3 "POSTGRES_USER" docker-compose.yml
grep -A 3 "POSTGRES_PASSWORD" docker-compose.yml

# They should match:
# Default: user=postgres, password=postgres

# 3. DATABASE_URL format
# postgresql+asyncpg://postgres:postgres@db:5432/footnote
#                      ^^^^^^^^  ^^^^^^^^
#                      must match POSTGRES_USER and POSTGRES_PASSWORD
```

### "Missing credentials" error on startup

**Problem**: Application won't start because API keys are missing

**Solution**:
```bash
# Check what's missing
./scripts/validate-credentials.sh local

# Make sure .env file exists
ls -la .env
# If not found: cp .env.example .env

# Fill in missing values
# See .env.example for where to get each credential

# Verify all required vars are set
grep -E "^(GOOGLE_CLIENT_ID|ANTHROPIC_API_KEY|FIREWORKS_API_KEY)=" .env
```

---

## Security Best Practices

### Never Commit Credentials

```bash
# Check that you haven't accidentally committed credentials
git log --all -p | grep -i "api_key\|password" | head

# Check staged files
git diff --cached | grep -i "api_key\|password"
```

### Rotate Credentials Regularly

```bash
# Once per quarter, regenerate API keys:
# 1. Go to each API provider's console
# 2. Generate new keys
# 3. Update .env file
# 4. Restart services
# 5. Delete old keys from provider console
```

### Use Different Credentials Per Environment

```bash
# Different API keys for:
# - Local development (can be permissive)
# - Staging (test full pipeline)
# - Production (most restrictive, audit logging)

.env              # Local development keys
.env.staging      # Staging keys (never commit)
.env.production   # Production keys (never commit, use secrets manager)
```

---

## Example Workflows

### Setting Up a New Developer Machine

```bash
# 1. Clone repository
git clone <repo>
cd <repo>

# 2. Copy template
cp .env.example .env

# 3. Ask for credentials (from team lead or 1Password/LastPass)
# Edit .env and paste credentials

# 4. Validate
./scripts/validate-credentials.sh local

# 5. Start services
npm run dev

# OR for Docker
./scripts/validate-credentials.sh docker
docker-compose up
```

### Switching Between Local and Docker

```bash
# Currently using local, switch to Docker
# Your .env already has localhost in DATABASE_URL

# Option 1: Use docker-compose with correct DATABASE_URL
docker-compose --env-file .env.docker up

# Option 2: Temporarily edit .env
sed -i '' 's/@localhost:/@db:/g' .env
docker-compose up

# Don't forget to restore it afterward!
sed -i '' 's/@db:/@localhost:/g' .env
```

### Debugging in CI/CD

```bash
# In GitHub Actions workflow
- name: Validate credentials
  run: ./scripts/validate-credentials.sh production

- name: Check no secrets are committed
  run: |
    if git log -p | grep -i "ANTHROPIC_API_KEY\|GOOGLE_CLIENT_SECRET"; then
      echo "ERROR: Credentials found in git history"
      exit 1
    fi
```

---

## Quick Reference

| Scenario | DATABASE_URL Hostname | Command |
|----------|----------------------|---------|
| Local development | `localhost` | `npm run dev` |
| Docker services | `db` | `docker-compose up` |
| Production AWS RDS | `your-db.rds.amazonaws.com` | Deploy via CD |
| Testing | `testdb` | `pytest --db=testdb` |

## Getting Help

1. **Read the error message carefully** - It usually tells you what's wrong
2. **Run validation script** - `./scripts/validate-credentials.sh <environment>`
3. **Check debug output** - `./scripts/debug-config.sh`
4. **See CREDENTIAL_MANAGEMENT.md** - For deeper technical details
5. **Ask the team** - Check team Slack/Discord for similar issues

---

**Last updated**: January 2026
**Related files**: CREDENTIAL_MANAGEMENT.md, .env.example, .env.docker
