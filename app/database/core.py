# app/database/core.py
"""
Core database connection and session management for coBoarding platform
Handles PostgreSQL connections with async support and connection pooling
"""

import os
import asyncio
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    AsyncEngine,
    async_sessionmaker
)
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy import text
import asyncpg
from loguru import logger

from .models import Base

# Global engine instance
engine: Optional[AsyncEngine] = None
async_session_factory: Optional[async_sessionmaker] = None


def get_database_url() -> str:
    """Get database URL from environment variables"""
    database_url = os.getenv('DATABASE_URL')

    if not database_url:
        # Fallback to individual components
        user = os.getenv('POSTGRES_USER', 'coboarding')
        password = os.getenv('POSTGRES_PASSWORD', 'secure_password_123')
        host = os.getenv('POSTGRES_HOST', 'localhost')
        port = os.getenv('POSTGRES_PORT', '5432')
        database = os.getenv('POSTGRES_DB', 'coboarding')

        database_url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"

    # Ensure we're using asyncpg driver
    if database_url.startswith('postgresql://'):
        database_url = database_url.replace('postgresql://', 'postgresql+asyncpg://', 1)

    return database_url


def create_engine() -> AsyncEngine:
    """Create SQLAlchemy async engine with optimal configuration"""
    database_url = get_database_url()
    
    # Configure engine with appropriate pool settings
    engine_kwargs = {
        "echo": os.getenv('SQL_ECHO', 'false').lower() == 'true',
        "pool_pre_ping": True,
        "pool_size": int(os.getenv('DB_POOL_SIZE', '5')),
        "max_overflow": int(os.getenv('DB_MAX_OVERFLOW', '10')),
        "pool_timeout": int(os.getenv('DB_POOL_TIMEOUT', '30')),
        "pool_recycle": int(os.getenv('DB_POOL_RECYCLE', '1800')),
    }
    
    # Use NullPool for SQLite to avoid thread issues
    if database_url.startswith('sqlite'):
        engine_kwargs = {
            "echo": engine_kwargs["echo"],
            "poolclass": NullPool
        }
    
    # Create the engine
    engine = create_async_engine(database_url, **engine_kwargs)
    
    logger.info(f"Database engine created with URL: {database_url.split('@')[-1]}")
    return engine


async def init_database() -> None:
    """Initialize database connection and create tables"""
    global engine, async_session_factory
    
    if engine is None:
        engine = create_engine()
    
    # Create session factory
    async_session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
        class_=AsyncSession
    )
    
    # Test connection and create tables
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))

        logger.info("✅ Database connection established successfully")

        # Create tables if they don't exist
        await create_tables()

        logger.info("✅ Database tables created successfully")

    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise


async def create_tables() -> None:
    """Create all database tables with appropriate indexes for the current database type."""
    global engine
    
    if engine is None:
        raise RuntimeError("Database engine not initialized")
    
    try:
        async with engine.begin() as conn:
            # Create tables
            await conn.run_sync(Base.metadata.create_all)

            # Get database dialect
            dialect = engine.dialect.name
            logger.info(f"Using database dialect: {dialect}")

            if dialect == 'postgresql':
                # PostgreSQL specific indexes and functions
                await conn.execute(text("""
                    -- Create additional indexes for performance
                    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_candidates_session_expires 
                    ON candidates(session_id, expires_at);

                    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_applications_status_score 
                    ON applications(status, match_score DESC);

                    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_notifications_retry 
                    ON notifications(delivery_status, next_retry_at) 
                    WHERE delivery_status = 'failed';

                    -- Create function for automatic cleanup
                    CREATE OR REPLACE FUNCTION cleanup_expired_data()
                    RETURNS INTEGER AS $$
                    DECLARE
                        deleted_count INTEGER := 0;
                    BEGIN
                        -- Delete expired candidates (cascades to applications and notifications)
                        DELETE FROM candidates WHERE expires_at < NOW();
                        RETURN deleted_count;
                    END;
                    $$ LANGUAGE plpgsql;
                """))
            elif dialect == 'sqlite':
                # SQLite specific indexes (no CONCURRENTLY support)
                await conn.execute(text("""
                    -- Create additional indexes for performance
                    CREATE INDEX IF NOT EXISTS idx_candidates_session_expires 
                    ON candidates(session_id, expires_at);

                    CREATE INDEX IF NOT EXISTS idx_applications_status_score 
                    ON applications(status, match_score);

                    CREATE INDEX IF NOT EXISTS idx_notifications_retry 
                    ON notifications(delivery_status, next_retry_at) 
                    WHERE delivery_status = 'failed';
                """))
                logger.info("Skipping PostgreSQL-specific functions for SQLite")
            else:
                logger.warning(f"Unsupported database dialect: {dialect}. Only basic tables will be created.")

    except Exception as e:
        logger.error(f"❌ Table creation failed: {e}")
        raise


async def close_database() -> None:
    """Close database connections"""
    global engine
    
    if engine:
        logger.info("Closing database connections...")
        await engine.dispose()
        logger.info("✅ Database connections closed")


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting database session in FastAPI
    Usage: async def endpoint(db: AsyncSession = Depends(get_db_session))
    """
    global async_session_factory
    
    if not async_session_factory:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_session() -> AsyncSession:
    """
    Context manager for getting database session
    Usage: async with get_session() as session:
    """
    global async_session_factory
    
    if not async_session_factory:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def test_connection() -> bool:
    """Test database connection"""
    global engine
    
    if not engine:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False


async def execute_raw_sql(query: str, params: dict = None) -> list:
    """Execute raw SQL query and return results"""
    global engine
    
    if not engine:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    
    async with engine.begin() as conn:
        result = await conn.execute(text(query), params or {})
        return [dict(row) for row in result]


async def get_connection_pool_status() -> dict:
    """Get connection pool status for monitoring"""
    global engine
    
    if not engine:
        return {"status": "not_initialized"}
    
    pool = engine.pool
    
    return {
        "status": "active",
        "size": pool.size(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "checkedin": pool.checkedin(),
    }
