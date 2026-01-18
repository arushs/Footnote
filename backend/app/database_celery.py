"""Synchronous database session factory for Celery workers.

Celery workers run tasks synchronously (even with asyncio.run() wrapper),
so they need blocking SQLAlchemy sessions instead of async ones.
"""

from celery.signals import task_postrun, worker_process_init
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from app.config import settings

# Convert async URL to sync URL for blocking operations
SYNC_DATABASE_URL = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")

# Create blocking engine for Celery workers
# Pool size should account for concurrency setting (--concurrency=20)
celery_engine = create_engine(
    SYNC_DATABASE_URL,
    pool_size=10,
    max_overflow=15,
    pool_pre_ping=True,
    pool_recycle=3600,
)

CelerySessionLocal = sessionmaker(bind=celery_engine, autoflush=False, autocommit=False)
CeleryScopedSession = scoped_session(CelerySessionLocal)


@task_postrun.connect
def cleanup_session(sender=None, **kwargs):
    """Clean up database session after each task."""
    CeleryScopedSession.remove()


@worker_process_init.connect
def init_worker(**kwargs):
    """Re-initialize connection pool when worker starts (important after fork)."""
    celery_engine.dispose()
