from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    pass


# Global engine and session for FastAPI (single event loop)
engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
    pool_recycle=settings.db_pool_recycle,
    pool_pre_ping=True,
    connect_args={
        "command_timeout": settings.db_command_timeout,
        "server_settings": {
            "statement_timeout": str(settings.db_statement_timeout_ms),
            "lock_timeout": "10000",  # 10 second lock timeout
        },
    },
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def create_task_session_factory() -> async_sessionmaker[AsyncSession]:
    """
    Create a fresh engine and session factory for use in Celery tasks.

    Each Celery task runs asyncio.run() which creates a new event loop.
    SQLAlchemy async engines are bound to the event loop they're first used on.
    This function creates a completely fresh engine/session for each task to
    avoid "bound to a different event loop" errors.

    Uses longer timeouts than API engine since Celery tasks process larger batches.
    """
    task_engine = create_async_engine(
        settings.database_url,
        echo=False,
        pool_size=settings.celery_db_pool_size,
        max_overflow=settings.celery_db_max_overflow,
        pool_recycle=settings.celery_db_pool_recycle,
        pool_pre_ping=True,
        connect_args={
            "command_timeout": settings.celery_db_command_timeout,
            "server_settings": {
                "statement_timeout": str(settings.celery_db_statement_timeout_ms),
                "lock_timeout": "30000",  # 30 second lock timeout for batch ops
            },
        },
    )
    return async_sessionmaker(task_engine, class_=AsyncSession, expire_on_commit=False)


@asynccontextmanager
async def get_task_session():
    """
    Get a database session for use in Celery tasks.

    Creates a fresh engine/session factory to avoid event loop conflicts.
    Automatically handles commit/rollback and closes the engine.
    Uses longer timeouts suited for batch processing.
    """
    task_engine = create_async_engine(
        settings.database_url,
        echo=False,
        pool_size=settings.celery_db_pool_size,
        max_overflow=settings.celery_db_max_overflow,
        pool_recycle=settings.celery_db_pool_recycle,
        pool_pre_ping=True,
        connect_args={
            "command_timeout": settings.celery_db_command_timeout,
            "server_settings": {
                "statement_timeout": str(settings.celery_db_statement_timeout_ms),
                "lock_timeout": "30000",  # 30 second lock timeout for batch ops
            },
        },
    )
    task_session_factory = async_sessionmaker(
        task_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with task_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await task_engine.dispose()
