"""Synchronous database session factory for Celery workers.

Celery workers run tasks synchronously (even with asyncio.run() wrapper),
so they need blocking SQLAlchemy sessions instead of async ones.
"""

from contextlib import contextmanager

from celery.signals import task_postrun, worker_process_init
from sqlalchemy import create_engine, event
from sqlalchemy.orm import scoped_session, sessionmaker

from app.config import settings

# Convert async URL to sync URL for blocking operations
SYNC_DATABASE_URL = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")

# Create blocking engine for Celery workers with configurable pool settings
celery_engine = create_engine(
    SYNC_DATABASE_URL,
    pool_size=settings.celery_db_pool_size,
    max_overflow=settings.celery_db_max_overflow,
    pool_pre_ping=True,
    pool_recycle=settings.celery_db_pool_recycle,
    pool_timeout=settings.db_pool_timeout,
)


@event.listens_for(celery_engine, "connect")
def set_celery_db_options(dbapi_conn, connection_record):
    """Set statement timeout for Celery database connections."""
    cursor = dbapi_conn.cursor()
    cursor.execute(f"SET statement_timeout = '{settings.celery_db_statement_timeout_ms}'")
    cursor.execute("SET lock_timeout = '30000'")  # 30 second lock timeout
    cursor.close()


CelerySessionLocal = sessionmaker(bind=celery_engine, autoflush=False, autocommit=False)
CeleryScopedSession = scoped_session(CelerySessionLocal)


@contextmanager
def celery_session_scope():
    """Provide a transactional scope around a series of operations.

    Usage:
        with celery_session_scope() as session:
            session.add(obj)
            # auto-commits on success, rolls back on exception
    """
    session = CeleryScopedSession()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        CeleryScopedSession.remove()


@task_postrun.connect
def cleanup_session(sender=None, **kwargs):
    """Clean up database session after each task."""
    CeleryScopedSession.remove()


@worker_process_init.connect
def init_worker(**kwargs):
    """Re-initialize connection pool when worker starts (important after fork)."""
    celery_engine.dispose()
