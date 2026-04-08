from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings


# --- Async engine (for FastAPI runtime) ---

_async_engine = None
_async_session_factory = None


def get_async_engine():
    global _async_engine
    if _async_engine is None:
        settings = get_settings()
        _async_engine = create_async_engine(
            settings.DATABASE_URL,
            echo=False,
            pool_size=10,
            max_overflow=20,
        )
    return _async_engine


def get_async_session_factory():
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            bind=get_async_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_factory


async def get_db():
    """FastAPI dependency that yields an async database session."""
    factory = get_async_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# --- Sync engine (for Alembic migrations & import CLI) ---

_sync_engine = None
_sync_session_factory = None


def get_sync_engine():
    global _sync_engine
    if _sync_engine is None:
        settings = get_settings()
        _sync_engine = create_engine(
            settings.DATABASE_URL_SYNC,
            echo=False,
            pool_size=10,
            max_overflow=20,
        )
    return _sync_engine


def get_sync_session_factory():
    global _sync_session_factory
    if _sync_session_factory is None:
        _sync_session_factory = sessionmaker(
            bind=get_sync_engine(),
            expire_on_commit=False,
        )
    return _sync_session_factory


# --- ORM Base ---

class Base(DeclarativeBase):
    pass
