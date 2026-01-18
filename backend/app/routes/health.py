"""Health check endpoints including Celery worker status."""

import asyncio
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException

from app.celery_app import celery_app

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
