"""Health check endpoints including Celery worker status and database connectivity."""

import asyncio
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.celery_app import celery_app
from app.config import settings
from app.database import get_db

router = APIRouter()

# Thread pool for running blocking Celery operations
_executor = ThreadPoolExecutor(max_workers=2)


def _sync_ping_workers() -> dict | None:
    """Synchronous worker ping - runs in thread pool."""
    inspect = celery_app.control.inspect()
    return inspect.ping()


@router.get("")
async def health():
    """Basic health check."""
    return {"status": "healthy"}


@router.get("/celery")
async def celery_health():
    """Check if Celery workers are responding (non-blocking)."""
    loop = asyncio.get_event_loop()
    try:
        ping = await loop.run_in_executor(_executor, _sync_ping_workers)
        if not ping:
            raise HTTPException(503, "No Celery workers available")
        return {"status": "healthy", "workers": list(ping.keys())}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(503, f"Celery health check failed: {e}") from e


@router.get("/db")
async def db_health(db: AsyncSession = Depends(get_db)):
    """Check database connectivity and verify timeout configuration.

    Returns the current statement_timeout setting to verify proper configuration.
    """
    try:
        # Simple query to verify connectivity
        result = await db.execute(text("SELECT 1"))
        result.scalar()

        # Get current timeout settings
        timeout_result = await db.execute(text("SHOW statement_timeout"))
        statement_timeout = timeout_result.scalar()

        return {
            "status": "healthy",
            "statement_timeout": statement_timeout,
            "expected_timeout_ms": settings.db_statement_timeout_ms,
        }
    except Exception as e:
        raise HTTPException(503, f"Database health check failed: {e}") from e
