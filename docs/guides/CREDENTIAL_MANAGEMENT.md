# Credential Management & Prevention Strategies

## Context: Database Credential Mismatch Issue

The root `.env` file uses `localhost` for the DATABASE_URL while `docker-compose.yml` uses `db` (the Docker service name) for hostname. This mismatch causes PostgreSQL authentication failures when running in containers.

**Root Cause:**
- Root `.env`: `postgresql+asyncpg://postgres:postgres@localhost:5432/footnote`
- Docker-compose backend service: `postgresql+asyncpg://postgres:postgres@db:5432/footnote`
- The `localhost` reference breaks inside containers where services communicate via service names

---

## 1. Prevention Strategies

### 1.1 Environment-Specific Configuration Files

**Implement separate credential files for different contexts:**

```
.env.local          # Local development with localhost
.env.docker         # Docker container communication
.env.production     # Production credentials
```

**Load strategy:**
- Use environment variable `APP_ENV` or `ENVIRONMENT` to determine which file to load
- Docker Compose can set `APP_ENV=docker` automatically
- Local development defaults to `APP_ENV=local`

**Benefits:**
- Clear separation of concerns
- Prevents accidental use of wrong credentials
- Easier to audit which credentials are used where

### 1.2 Configuration Validation on Startup

**Add startup validation script to check credential consistency:**

```python
# backend/config_validator.py
import os
from urllib.parse import urlparse

def validate_database_credentials():
    """Validate database configuration on startup"""
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError("DATABASE_URL not set")

    # Parse the URL
    parsed = urlparse(database_url)
    hostname = parsed.hostname
    port = parsed.port or 5432

    # Validation rules
    if os.getenv("RUNNING_IN_DOCKER") == "true":
        # Inside Docker, should use service name (db), not localhost
        if hostname in ["localhost", "127.0.0.1"]:
            raise ValueError(
                f"Invalid DATABASE_URL for Docker environment. "
                f"Using '{hostname}' instead of Docker service name 'db'. "
                f"DATABASE_URL={database_url}"
            )
    else:
        # Local development should use localhost
        if hostname != "localhost" and hostname != "127.0.0.1":
            raise ValueError(
                f"Invalid DATABASE_URL for local environment. "
                f"Expected 'localhost', got '{hostname}'. "
                f"DATABASE_URL={database_url}"
            )

    return True

# In main.py startup event
@app.on_event("startup")
async def startup_validation():
    validate_database_credentials()
```

**Add to docker-compose.yml:**
```yaml
environment:
  RUNNING_IN_DOCKER: "true"
  APP_ENV: "docker"
```

### 1.3 Docker Compose Environment Variable Substitution

**Use a `.env.docker` file that docker-compose automatically sources:**

```bash
# docker-compose.yml services
backend:
  environment:
    DATABASE_URL: ${DATABASE_URL:-postgresql+asyncpg://postgres:postgres@db:5432/footnote}
    # Other credentials...
```

**Create `.env.docker`:**
```
# Database credentials for Docker
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/footnote
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=footnote

# Other credentials use same format as root .env
GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID}
GOOGLE_CLIENT_SECRET=${GOOGLE_CLIENT_SECRET}
# ... etc
```

**Docker Compose will automatically load `.env.docker` if explicitly referenced:**
```yaml
version: '3.8'
env_file:
  - .env.docker
  - .env  # Fallback for credentials

services:
  backend:
    environment:
      DATABASE_URL: ${DATABASE_URL}
```

### 1.4 Pre-Deployment Credential Check Script

**Create a validation script that runs before docker-compose up:**

```bash
#!/bin/bash
# scripts/validate-credentials.sh

set -e

echo "Validating credential configuration..."

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "ERROR: Root .env file not found"
    exit 1
fi

# Extract DATABASE_URL from root .env
ROOT_DB_URL=$(grep "DATABASE_URL=" .env | cut -d'=' -f2)
DOCKER_DB_URL="postgresql+asyncpg://postgres:postgres@db:5432/footnote"

# Extract hostname from URL
extract_hostname() {
    echo "$1" | sed -E 's|.*://[^@]*@([^:]+).*|\1|'
}

ROOT_HOST=$(extract_hostname "$ROOT_DB_URL")
DOCKER_HOST=$(extract_hostname "$DOCKER_DB_URL")

# Validate for Docker environment
if [ "$1" == "docker" ]; then
    if [ "$ROOT_HOST" != "db" ]; then
        echo "WARNING: Root .env DATABASE_URL uses '$ROOT_HOST' instead of 'db'"
        echo "This may cause connection issues in Docker containers."
        echo ""
        echo "Expected in docker-compose.yml:"
        echo "DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/footnote"
        echo ""
        echo "But your .env has:"
        echo "DATABASE_URL=$ROOT_DB_URL"
        read -p "Continue anyway? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
fi

# Check for missing credentials
REQUIRED_VARS=(
    "GOOGLE_CLIENT_ID"
    "GOOGLE_CLIENT_SECRET"
    "ANTHROPIC_API_KEY"
    "FIREWORKS_API_KEY"
    "MISTRAL_API_KEY"
    "SECRET_KEY"
)

MISSING_VARS=()
for var in "${REQUIRED_VARS[@]}"; do
    if ! grep -q "^$var=" .env; then
        MISSING_VARS+=("$var")
    fi
done

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    echo "ERROR: Missing required environment variables:"
    printf '%s\n' "${MISSING_VARS[@]}"
    exit 1
fi

echo "✓ All credential validations passed"
exit 0
```

**Use in docker setup:**
```bash
# Before running docker-compose
./scripts/validate-credentials.sh docker
docker-compose up
```

### 1.5 Git Hooks to Prevent Credential Leaks

**Create a pre-commit hook to prevent sensitive files from being committed:**

```bash
#!/bin/bash
# .git/hooks/pre-commit

echo "Checking for credential files..."

# Files that should never be committed
PROTECTED_FILES=(
    ".env"
    ".env.local"
    ".env.production"
    "backend/.env"
    "frontend/.env"
    "*.key"
    "credentials.json"
)

STAGED_FILES=$(git diff --cached --name-only)

for protected_file in "${PROTECTED_FILES[@]}"; do
    for staged_file in $STAGED_FILES; do
        if [ "$staged_file" = "$protected_file" ]; then
            echo "ERROR: Attempting to commit protected file: $staged_file"
            echo "Use .gitignore or .env.example instead"
            exit 1
        fi
    done
done

exit 0
```

---

## 2. Best Practices for Managing Credentials

### 2.1 Use Example Files as Source of Truth

**Maintain `.env.example` files that are committed to git:**

```
backend/.env.example
frontend/.env.example
.env.example
```

**Template format with clear separation:**
```env
# Database (adjust hostname based on environment)
# LOCAL: localhost
# DOCKER: db
# PRODUCTION: your-rds-endpoint.aws.com
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/footnote

# Required for authentication
GOOGLE_CLIENT_ID=your-value
GOOGLE_CLIENT_SECRET=your-value
```

### 2.2 Document Environment-Specific Values

**Create `ENVIRONMENT_SETUP.md`:**

```markdown
## Environment Variable Setup

### Local Development
Use `localhost` for all service connections:
- DATABASE_URL: `postgresql+asyncpg://postgres:postgres@localhost:5432/footnote`
- REDIS_URL: `redis://localhost:6379` (if applicable)

### Docker Environment
Use Docker service names for inter-service communication:
- DATABASE_URL: `postgresql+asyncpg://postgres:postgres@db:5432/footnote`
- Backend to Frontend: `http://frontend:3000`

### Production
Use actual endpoints:
- DATABASE_URL: `postgresql+asyncpg://user:password@your-db-host:5432/prod_db`
- Use environment variables from deployment platform (AWS Secrets Manager, etc.)
```

### 2.3 Centralize Credential Validation

**Create a configuration module that handles all environment setup:**

```python
# backend/config.py
import os
from pydantic import Field, validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application configuration from environment variables"""

    # Database
    database_url: str = Field(default="postgresql+asyncpg://postgres:postgres@localhost:5432/footnote")
    running_in_docker: bool = Field(default=False)

    # API Keys
    google_client_id: str = Field(default="")
    google_client_secret: str = Field(default="")
    anthropic_api_key: str = Field(default="")
    fireworks_api_key: str = Field(default="")
    mistral_api_key: str = Field(default="")

    @validator('database_url')
    def validate_database_url(cls, v, values):
        """Validate database URL matches environment"""
        if values.get('running_in_docker'):
            if 'localhost' in v or '127.0.0.1' in v:
                raise ValueError(
                    f"Database URL contains localhost in Docker environment: {v}"
                )
        return v

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()

# Use throughout app
from config import settings
async def connect_db():
    await database.connect(settings.database_url)
```

### 2.4 CI/CD Integration

**Add credential validation to CI pipeline (GitHub Actions example):**

```yaml
# .github/workflows/validate-config.yml
name: Validate Configuration

on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Check .env files not committed
        run: |
          if git diff HEAD~1 | grep -E '^\+.*DATABASE_URL.*='; then
            echo "ERROR: .env files should not be committed"
            exit 1
          fi

      - name: Validate example files exist
        run: |
          [ -f ".env.example" ] || { echo ".env.example missing"; exit 1; }
          [ -f "backend/.env.example" ] || { echo "backend/.env.example missing"; exit 1; }

      - name: Check consistency between example files
        run: |
          # Extract variable names from examples
          VARS=$(grep -h "^[A-Z_]*=" .env.example backend/.env.example | cut -d'=' -f1 | sort -u)
          echo "Required variables: $VARS"
```

### 2.5 Local Development Setup Script

**Create an interactive setup script:**

```bash
#!/bin/bash
# scripts/setup-dev.sh

echo "Setting up local development environment..."
echo ""

# Check if .env exists
if [ -f ".env" ]; then
    read -p ".env already exists. Overwrite? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Keeping existing .env"
        exit 0
    fi
fi

# Copy from example
cp .env.example .env
cp backend/.env.example backend/.env

echo "Created .env files from examples"
echo ""
echo "Now you need to fill in the values:"
echo "  1. Open .env and add your API keys"
echo "  2. For local development, use DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/footnote"
echo "  3. Run: npm run db:setup  (to initialize the database)"
echo ""
echo "To start the application:"
echo "  - Local only: npm run dev"
echo "  - With Docker: docker-compose up"
```

---

## 3. Validation Steps & Checks

### 3.1 Pre-Docker Launch Checklist

**Create `DOCKER_STARTUP.md`:**

```markdown
# Docker Startup Checklist

Before running `docker-compose up`:

- [ ] .env file exists at project root
- [ ] .env contains all required credentials (check against .env.example)
- [ ] DATABASE_URL in .env uses `db` as hostname (not localhost)
- [ ] All API keys are valid (GOOGLE, ANTHROPIC, FIREWORKS, MISTRAL)
- [ ] SECRET_KEY is a secure random string (at minimum 32 characters)
- [ ] FRONTEND_URL matches your deployment domain
- [ ] Run validation script: `./scripts/validate-credentials.sh docker`

Common issues:
- Using `localhost` in DATABASE_URL inside Docker → Use `db` instead
- Missing .env file → Copy from .env.example
- Outdated API keys → Check and update in .env
```

### 3.2 Automated Health Checks

**Add health check endpoints:**

```python
# backend/main.py
@app.get("/health/config")
async def config_health():
    """Check if configuration is valid"""
    try:
        # Verify database connection works
        async with database.connection() as conn:
            await conn.fetch("SELECT 1")

        # Verify API keys are set
        missing_keys = []
        required_keys = [
            "GOOGLE_CLIENT_ID",
            "GOOGLE_CLIENT_SECRET",
            "ANTHROPIC_API_KEY"
        ]

        for key in required_keys:
            if not os.getenv(key):
                missing_keys.append(key)

        if missing_keys:
            return {
                "status": "degraded",
                "missing_credentials": missing_keys
            }

        return {"status": "healthy"}

    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }

# In docker-compose.yml health check
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health/config"]
  interval: 30s
  timeout: 10s
  retries: 3
```

### 3.3 Logging & Debugging Tools

**Create debug script to show current configuration:**

```bash
#!/bin/bash
# scripts/debug-config.sh

echo "Current Configuration (sanitized)"
echo "===================================="
echo ""

echo "Environment Detection:"
echo "  RUNNING_IN_DOCKER: ${RUNNING_IN_DOCKER:-not set}"
echo "  APP_ENV: ${APP_ENV:-not set}"
echo ""

echo "Database Configuration:"
if [ -f ".env" ]; then
    DB_URL=$(grep "DATABASE_URL=" .env | cut -d'=' -f2)
    # Extract components
    HOSTNAME=$(echo "$DB_URL" | sed -E 's|.*://[^@]*@([^:]+).*|\1|')
    PORT=$(echo "$DB_URL" | sed -E 's|.*:([0-9]+).*|\1|')
    DATABASE=$(echo "$DB_URL" | sed -E 's|.*\/([^?]*)?.*|\1|')

    echo "  Hostname: $HOSTNAME"
    echo "  Port: $PORT"
    echo "  Database: $DATABASE"
    echo "  Full URL: $DB_URL"
else
    echo "  ERROR: .env not found"
fi

echo ""
echo "API Keys Status:"
for key in GOOGLE_CLIENT_ID ANTHROPIC_API_KEY FIREWORKS_API_KEY MISTRAL_API_KEY; do
    VALUE=$(grep "^$key=" .env 2>/dev/null | cut -d'=' -f2)
    if [ -z "$VALUE" ]; then
        echo "  $key: NOT SET"
    else
        # Show first 10 chars + asterisks
        PREFIX=$(echo "$VALUE" | cut -c1-10)
        echo "  $key: ${PREFIX}***"
    fi
done
```

### 3.4 Docker Compose Validation

**Add validation service:**

```yaml
# docker-compose.yml
services:
  config-validator:
    image: python:3.11-slim
    entrypoint: |
      bash -c "
      set -e
      echo 'Validating configuration...'

      # Check environment variables
      test -n '${DATABASE_URL}' || (echo 'DATABASE_URL not set'; exit 1)
      test -n '${ANTHROPIC_API_KEY}' || (echo 'ANTHROPIC_API_KEY not set'; exit 1)

      # Validate DATABASE_URL format
      if echo '${DATABASE_URL}' | grep -q 'localhost\|127.0.0.1'; then
          echo 'ERROR: DATABASE_URL contains localhost in Docker context'
          exit 1
      fi

      echo 'Configuration validation passed!'
      "
    env_file:
      - .env.docker
      - .env
    depends_on:
      - db
```

---

## 4. Implementation Roadmap

### Phase 1: Immediate (Prevent Current Issue)
- [ ] Create `.env.docker` with correct database credentials
- [ ] Update docker-compose.yml to use separate env file
- [ ] Add validation script and document in README

### Phase 2: Short-term (Add Safety)
- [ ] Create `.env.example` files for all directories
- [ ] Implement startup validation in Python
- [ ] Add pre-commit hooks
- [ ] Create ENVIRONMENT_SETUP.md documentation

### Phase 3: Medium-term (Automate Checks)
- [ ] Add CI/CD credential validation
- [ ] Implement config health check endpoint
- [ ] Create debug script for troubleshooting

### Phase 4: Long-term (Production-Ready)
- [ ] Integrate with AWS Secrets Manager or similar
- [ ] Implement credential rotation mechanisms
- [ ] Add audit logging for credential access
- [ ] Create credential validation in CD pipeline

---

## 5. Quick Reference

### When Starting Services

**Local Development:**
```bash
# Ensure .env uses localhost
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/footnote
npm run dev
```

**Docker:**
```bash
# Ensure .env or .env.docker uses 'db' service name
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/footnote
./scripts/validate-credentials.sh docker
docker-compose up
```

**Production:**
```bash
# Use actual RDS/managed database endpoint
DATABASE_URL=postgresql+asyncpg://user:password@your-prod-db.rds.amazonaws.com:5432/production_db
# Deploy via your CI/CD pipeline
```

### Files to Keep in Git

- `.env.example` - Template for local development
- `backend/.env.example` - Backend-specific template
- `.github/workflows/validate-config.yml` - CI validation
- `scripts/validate-credentials.sh` - Validation script
- `ENVIRONMENT_SETUP.md` - Setup documentation

### Files to Add to .gitignore

```
.env
.env.local
.env.docker
.env.production
.env.*.local
backend/.env
frontend/.env
*.key
credentials.json
```

---

## Summary

Prevent credential mismatches by:

1. **Separating environments** - Different .env files for local vs docker vs production
2. **Validating early** - Check credentials on startup and before deployment
3. **Documenting explicitly** - Clear guides on what goes where
4. **Automating checks** - CI/CD and pre-commit hooks catch issues
5. **Centralizing config** - Single source of truth for validation logic
6. **Testing thoroughly** - Health checks ensure configuration is correct

The key insight: **localhost works locally, service names work in Docker, actual endpoints in production**.
