"""Database engine configuration and session management."""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from insight_engine.config import settings
from insight_engine.exceptions import DatabaseException
from insight_engine.logging_config import get_logger
from insight_engine.models.base import Base

logger = get_logger(__name__)

# Global engine and session factory
_async_engine: Optional[AsyncEngine] = None
_async_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def get_database_url() -> str:
    """Get the database URL from configuration."""
    # For now, we'll use SQLite for development
    # In production, this should be PostgreSQL
    if settings.ENVIRONMENT == "production":
        # TODO: Add PostgreSQL configuration
        raise DatabaseException("PostgreSQL configuration not implemented yet")
    else:
        # Use SQLite for development
        return "sqlite+aiosqlite:///./insight_engine.db"


def get_database_engine() -> AsyncEngine:
    """Get or create the async database engine."""
    global _async_engine
    
    if _async_engine is None:
        database_url = get_database_url()
        
        # Configure engine based on database type
        if "sqlite" in database_url:
            # SQLite-specific configuration
            _async_engine = create_async_engine(
                database_url,
                echo=settings.DEBUG,
                poolclass=StaticPool,
                connect_args={
                    "check_same_thread": False,
                    "timeout": 20,
                },
                pool_pre_ping=True,
            )
        else:
            # PostgreSQL configuration
            _async_engine = create_async_engine(
                database_url,
                echo=settings.DEBUG,
                pool_size=20,
                max_overflow=30,
                pool_timeout=30,
                pool_recycle=3600,
                pool_pre_ping=True,
            )
        
        logger.info(f"Database engine created for: {database_url}")
    
    return _async_engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create the async session factory."""
    global _async_session_factory
    
    if _async_session_factory is None:
        engine = get_database_engine()
        _async_session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        logger.info("Database session factory created")
    
    return _async_session_factory


@asynccontextmanager
async def get_database_session() -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session with automatic cleanup."""
    session_factory = get_session_factory()
    
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise DatabaseException(f"Database operation failed: {e}")
        finally:
            await session.close()


async def create_database_tables() -> None:
    """Create all database tables."""
    try:
        engine = get_database_engine()
        
        async with engine.begin() as conn:
            # Create all tables
            await conn.run_sync(Base.metadata.create_all)
            
        logger.info("Database tables created successfully")
        
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
        raise DatabaseException(f"Failed to create database tables: {e}")


async def drop_database_tables() -> None:
    """Drop all database tables."""
    try:
        engine = get_database_engine()
        
        async with engine.begin() as conn:
            # Drop all tables
            await conn.run_sync(Base.metadata.drop_all)
            
        logger.info("Database tables dropped successfully")
        
    except Exception as e:
        logger.error(f"Failed to drop database tables: {e}")
        raise DatabaseException(f"Failed to drop database tables: {e}")


async def check_database_connection() -> bool:
    """Check if database connection is working."""
    try:
        async with get_database_session() as session:
            # Simple query to test connection
            result = await session.execute(text("SELECT 1"))
            return result.scalar() == 1
            
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False


async def initialize_database() -> None:
    """Initialize the database with tables and initial data."""
    try:
        logger.info("Initializing database...")
        
        # Create tables
        await create_database_tables()
        
        # TODO: Add initial data seeding if needed
        # await seed_initial_data()
        
        logger.info("Database initialization completed")
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise DatabaseException(f"Database initialization failed: {e}")


async def close_database_connections() -> None:
    """Close all database connections."""
    global _async_engine, _async_session_factory
    
    if _async_engine:
        await _async_engine.dispose()
        _async_engine = None
        logger.info("Database engine disposed")
    
    _async_session_factory = None
    logger.info("Database connections closed")