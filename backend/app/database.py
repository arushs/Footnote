from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    pass


# Global engine and session for FastAPI (single event loop)
engine = create_async_engine(settings.database_url, echo=False)
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
    """
    task_engine = create_async_engine(settings.database_url, echo=False)
    return async_sessionmaker(task_engine, class_=AsyncSession, expire_on_commit=False)


@asynccontextmanager
async def get_task_session():
    """
    Get a database session for use in Celery tasks.

    Creates a fresh engine/session factory to avoid event loop conflicts.
    Automatically handles commit/rollback and closes the engine.
    """
    task_engine = create_async_engine(settings.database_url, echo=False)
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
