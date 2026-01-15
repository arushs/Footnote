# Credential Configuration Checklist

Use this checklist before starting development or deploying services.

## Local Development Setup

- [ ] `.env.example` exists at project root
- [ ] Copied `.env.example` to `.env` (`cp .env.example .env`)
- [ ] All API keys filled in `.env` (not placeholder values)
- [ ] `DATABASE_URL` in `.env` uses **`localhost`** hostname
  - Correct: `postgresql+asyncpg://postgres:postgres@localhost:5432/...`
  - Wrong: `postgresql+asyncpg://postgres:postgres@db:5432/...`
- [ ] PostgreSQL is running locally (check with `psql -V`)
- [ ] Ran validation: `./scripts/validate-credentials.sh local`
- [ ] All services start without credential errors

## Docker Setup

- [ ] `.env` file exists with API keys filled in
- [ ] `.env.docker` file exists (or use correct DATABASE_URL in .env)
- [ ] `DATABASE_URL` uses **`db`** hostname (Docker service name)
  - Correct: `postgresql+asyncpg://postgres:postgres@db:5432/...`
  - Wrong: `postgresql+asyncpg://postgres:postgres@localhost:5432/...`
- [ ] `docker-compose.yml` database service name is `db` (not `postgres`, `database`, etc.)
- [ ] `docker-compose.yml` backend/worker services reference correct `DATABASE_URL`
- [ ] Ran validation: `./scripts/validate-credentials.sh docker`
- [ ] All containers are healthy after `docker-compose up`
- [ ] Backend can connect to database (check logs: `docker-compose logs backend`)

## Before Committing

- [ ] `.env` file is **NOT** staged for commit
  - Check: `git status | grep ".env"`
  - Should be empty or show only `.env.example`
- [ ] `.gitignore` includes `.env` patterns
  - Check: `grep "^\.env" .gitignore`
- [ ] Pre-commit hook is installed
  - Check: `ls -l .git/hooks/pre-commit`
  - Install if missing: `cp scripts/pre-commit-hook.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit`
- [ ] No API keys in commit message history
  - Check: `git log -p | grep -i "api_key\|secret" | head` (should be empty)

## Before Pushing to GitHub

- [ ] Repository is private OR `.env` patterns strictly in `.gitignore`
- [ ] `.env.example` contains only placeholders, no real credentials
- [ ] No recent commits contain credentials
  - Check: `git log --all -p -- .env* | head -50`
- [ ] Branch is up to date with main
- [ ] CI/CD will validate credentials exist in deployment environment

## Production Deployment

- [ ] Credentials stored in secrets manager (AWS Secrets, GitHub Secrets, etc.)
- [ ] `DATABASE_URL` points to production database endpoint
  - Example: `postgresql+asyncpg://user:pass@prod-db.rds.amazonaws.com:5432/prod_db`
- [ ] Ran validation: `./scripts/validate-credentials.sh production`
- [ ] Different API keys used for production vs development
- [ ] Credentials are never committed to git (only placeholder .env.example)
- [ ] Deployment pipeline has access to secrets manager
- [ ] All services start and connect successfully

## Regular Maintenance

Every 3 months:
- [ ] Review which API keys are in use
- [ ] Rotate old/unused credentials
- [ ] Update `.env.example` if new credentials added
- [ ] Review who has access to production credentials
- [ ] Check for any accidentally committed credentials: `git log -p -- ":(exclude).git" | grep -i "api_key\|password" | wc -l`

## Troubleshooting

If you encounter credential issues:

1. **Run validation script**: `./scripts/validate-credentials.sh <environment>`
2. **Check debug output**: `./scripts/debug-config.sh`
3. **Verify DATABASE_URL**:
   - Local: Must use `localhost`
   - Docker: Must use `db` (the service name)
   - Production: Must use actual database endpoint
4. **Look for hostname issues**:
   ```bash
   grep DATABASE_URL .env
   # Check if hostname matches your environment
   ```
5. **Check logs**:
   ```bash
   # Local
   tail -f logs/app.log

   # Docker
   docker-compose logs -f backend
   docker-compose logs -f db
   ```

## Helpful Commands

```bash
# Validate configuration
./scripts/validate-credentials.sh local
./scripts/validate-credentials.sh docker
./scripts/validate-credentials.sh production

# Debug configuration
./scripts/debug-config.sh

# Check what would be committed
git status
git diff --cached

# View current .env (sanitized)
sed 's/=.*/=***/' .env

# Test database connection
psql postgresql://postgres:postgres@localhost:5432/talk_to_folder

# Test from Docker
docker-compose exec backend psql -h db -U postgres -d talk_to_folder -c "SELECT 1"

# Install pre-commit hook
cp scripts/pre-commit-hook.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

## Key Principle

**The database hostname must match your environment:**
- **Local development**: `localhost` (direct connection)
- **Docker containers**: `db` (Docker service name)
- **Production**: `your-prod-endpoint.com` (managed database)

Using the wrong hostname is the #1 cause of credential/connection failures.

---

**Related documentation**:
- `CREDENTIAL_MANAGEMENT.md` - Detailed prevention strategies
- `ENVIRONMENT_SETUP.md` - Step-by-step setup guide
- `.env.example` - Template with all required fields
