# =============================================================================
# Stage 1: Base image with Python and uv
# =============================================================================
FROM python:3.13-slim AS base

# Install uv for fast package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# =============================================================================
# Stage 2: Development image with hot reload
# =============================================================================
FROM base AS development

# Copy dependency files (lock file ensures reproducible installs)
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --no-install-project

# Copy application code
COPY . .

# Install the project
RUN uv sync

EXPOSE 8000

# Default command for development (with hot reload)
CMD ["uv", "run", "uvicorn", "main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]

# =============================================================================
# Stage 3: Production build
# =============================================================================
FROM base AS production

# Install psql for running migrations
RUN apt-get update && apt-get install -y postgresql-client && rm -rf /var/lib/apt/lists/*

# Copy dependency files and install
COPY pyproject.toml uv.lock ./
RUN uv sync --no-install-project --no-dev

# Copy application code
COPY . .

# Install project
RUN uv sync --no-dev

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Production command
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
