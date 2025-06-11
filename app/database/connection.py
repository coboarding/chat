# app/database/connection.py
"""
Database connection and session management for coBoarding platform
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
from sqlalchemy.pool import QueuePool
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

    return create_async_engine(
        database_url,
        # Connection pool settings
        poolclass=QueuePool,
        pool_size=10,  # Number of connections to maintain
        max_overflow=20,  # Additional connections allowed
        pool_pre_ping=True,  # Validate connections before use
        pool_recycle=3600,  # Recycle connections after 1 hour

        # Query settings
        echo=os.getenv('ENVIRONMENT') == 'development',  # Log SQL queries in dev
        future=True,  # Use SQLAlchemy 2.0 style

        # Connection arguments
        connect_args={
            "server_settings": {
                "jit": "off",  # Disable JIT for faster query planning
                "application_name": "coboarding_api",
            },
            "command_timeout": 30,  # 30 second query timeout
            "statement_cache_size": 0,  # Disable prepared statement cache
        }
    )


async def init_database() -> None:
    """Initialize database connection and create tables"""
    global engine, async_session_factory

    try:
        logger.info("Initializing database connection...")

        # Create engine
        engine = create_engine()

        # Create session factory
        async_session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=True,
            autocommit=False
        )

        # Test connection
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))

        logger.info("✅ Database connection established successfully")

        # Create tables if they don't exist
        await create_tables()

    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise


async def create_tables() -> None:
    """Create all database tables"""
    global engine

    if not engine:
        raise RuntimeError("Database engine not initialized")

    try:
        logger.info("Creating database tables...")

        async with engine.begin() as conn:
            # Create tables
            await conn.run_sync(Base.metadata.create_all)

            # Create indexes and constraints
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
                    GET DIAGNOSTICS deleted_count = ROW_COUNT;

                    -- Delete old audit logs
                    DELETE FROM audit_logs WHERE retention_until < NOW();

                    -- Update job listing application counts
                    UPDATE job_listings 
                    SET applications_count = (
                        SELECT COUNT(*) 
                        FROM applications 
                        WHERE job_listing_id = job_listings.id
                    );

                    RETURN deleted_count;
                END;
                $$ LANGUAGE plpgsql;

                -- Create trigger for updating application counts
                CREATE OR REPLACE FUNCTION update_application_count()
                RETURNS TRIGGER AS $$
                BEGIN
                    IF TG_OP = 'INSERT' THEN
                        UPDATE job_listings 
                        SET applications_count = applications_count + 1
                        WHERE id = NEW.job_listing_id;
                        RETURN NEW;
                    ELSIF TG_OP = 'DELETE' THEN
                        UPDATE job_listings 
                        SET applications_count = GREATEST(applications_count - 1, 0)
                        WHERE id = OLD.job_listing_id;
                        RETURN OLD;
                    END IF;
                    RETURN NULL;
                END;
                $$ LANGUAGE plpgsql;

                DROP TRIGGER IF EXISTS trigger_application_count ON applications;
                CREATE TRIGGER trigger_application_count
                    AFTER INSERT OR DELETE ON applications
                    FOR EACH ROW EXECUTE FUNCTION update_application_count();
            """))

        logger.info("✅ Database tables created successfully")

    except Exception as e:
        logger.error(f"❌ Table creation failed: {e}")
        raise


async def close_database() -> None:
    """Close database connections"""
    global engine

    if engine:
        logger.info("Closing database connections...")


# app/database/connection.py
"""
Database connection and session management for coBoarding platform
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
from sqlalchemy.pool import QueuePool
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

    return create_async_engine(
        database_url,
        # Connection pool settings
        poolclass=QueuePool,
        pool_size=10,  # Number of connections to maintain
        max_overflow=20,  # Additional connections allowed
        pool_pre_ping=True,  # Validate connections before use
        pool_recycle=3600,  # Recycle connections after 1 hour

        # Query settings
        echo=os.getenv('ENVIRONMENT') == 'development',  # Log SQL queries in dev
        future=True,  # Use SQLAlchemy 2.0 style

        # Connection arguments
        connect_args={
            "server_settings": {
                "jit": "off",  # Disable JIT for faster query planning
                "application_name": "coboarding_api",
            },
            "command_timeout": 30,  # 30 second query timeout
            "statement_cache_size": 0,  # Disable prepared statement cache
        }
    )


async def init_database() -> None:
    """Initialize database connection and create tables"""
    global engine, async_session_factory

    try:
        logger.info("Initializing database connection...")

        # Create engine
        engine = create_engine()

        # Create session factory
        async_session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=True,
            autocommit=False
        )

        # Test connection
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))

        logger.info("✅ Database connection established successfully")

        # Create tables if they don't exist
        await create_tables()

    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise


async def create_tables() -> None:
    """Create all database tables"""
    global engine

    if not engine:
        raise RuntimeError("Database engine not initialized")

    try:
        logger.info("Creating database tables...")

        async with engine.begin() as conn:
            # Create tables
            await conn.run_sync(Base.metadata.create_all)

            # Create indexes and constraints
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
                RETURNS INTEGER AS $
                DECLARE
                    deleted_count INTEGER := 0;
                BEGIN
                    -- Delete expired candidates (cascades to applications and notifications)
                    DELETE FROM candidates WHERE expires_at < NOW();
                    GET DIAGNOSTICS deleted_count = ROW_COUNT;

                    -- Delete old audit logs
                    DELETE FROM audit_logs WHERE retention_until < NOW();

                    -- Update job listing application counts
                    UPDATE job_listings 
                    SET applications_count = (
                        SELECT COUNT(*) 
                        FROM applications 
                        WHERE job_listing_id = job_listings.id
                    );

                    RETURN deleted_count;
                END;
                $ LANGUAGE plpgsql;

                -- Create trigger for updating application counts
                CREATE OR REPLACE FUNCTION update_application_count()
                RETURNS TRIGGER AS $
                BEGIN
                    IF TG_OP = 'INSERT' THEN
                        UPDATE job_listings 
                        SET applications_count = applications_count + 1
                        WHERE id = NEW.job_listing_id;
                        RETURN NEW;
                    ELSIF TG_OP = 'DELETE' THEN
                        UPDATE job_listings 
                        SET applications_count = GREATEST(applications_count - 1, 0)
                        WHERE id = OLD.job_listing_id;
                        RETURN OLD;
                    END IF;
                    RETURN NULL;
                END;
                $ LANGUAGE plpgsql;

                DROP TRIGGER IF EXISTS trigger_application_count ON applications;
                CREATE TRIGGER trigger_application_count
                    AFTER INSERT OR DELETE ON applications
                    FOR EACH ROW EXECUTE FUNCTION update_application_count();
            """))

        logger.info("✅ Database tables created successfully")

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
        return False

    try:
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1 as test"))
            row = result.fetchone()
            return row[0] == 1
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False


async def execute_raw_sql(query: str, params: dict = None) -> list:
    """Execute raw SQL query and return results"""
    global engine

    if not engine:
        raise RuntimeError("Database not initialized")

    async with engine.begin() as conn:
        if params:
            result = await conn.execute(text(query), params)
        else:
            result = await conn.execute(text(query))

        return result.fetchall()


async def get_database_stats() -> dict:
    """Get database statistics for monitoring"""
    try:
        stats_query = """
        SELECT 
            'candidates' as table_name,
            COUNT(*) as total_count,
            COUNT(*) FILTER (WHERE expires_at > NOW()) as active_count,
            COUNT(*) FILTER (WHERE expires_at <= NOW()) as expired_count
        FROM candidates
        UNION ALL
        SELECT 
            'job_listings' as table_name,
            COUNT(*) as total_count,
            COUNT(*) FILTER (WHERE active = true) as active_count,
            COUNT(*) FILTER (WHERE active = false) as expired_count
        FROM job_listings
        UNION ALL
        SELECT 
            'applications' as table_name,
            COUNT(*) as total_count,
            COUNT(*) FILTER (WHERE status NOT IN ('rejected', 'withdrawn')) as active_count,
            COUNT(*) FILTER (WHERE status IN ('rejected', 'withdrawn')) as expired_count
        FROM applications
        UNION ALL
        SELECT 
            'notifications' as table_name,
            COUNT(*) as total_count,
            COUNT(*) FILTER (WHERE delivery_status = 'delivered') as active_count,
            COUNT(*) FILTER (WHERE delivery_status = 'failed') as expired_count
        FROM notifications;
        """

        results = await execute_raw_sql(stats_query)

        stats = {}
        for row in results:
            table_name, total, active, expired = row
            stats[table_name] = {
                'total': total,
                'active': active,
                'expired': expired
            }

        return stats

    except Exception as e:
        logger.error(f"Failed to get database stats: {e}")
        return {}


async def run_cleanup() -> dict:
    """Run database cleanup and return results"""
    try:
        cleanup_query = "SELECT cleanup_expired_data();"
        result = await execute_raw_sql(cleanup_query)

        deleted_count = result[0][0] if result else 0

        logger.info(f"Database cleanup completed: {deleted_count} records deleted")

        return {
            'success': True,
            'deleted_count': deleted_count,
            'timestamp': asyncio.get_event_loop().time()
        }

    except Exception as e:
        logger.error(f"Database cleanup failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'timestamp': asyncio.get_event_loop().time()
        }


# Utility functions for common database operations
async def get_or_create_candidate_by_email(session: AsyncSession, email: str, **candidate_data) -> tuple:
    """
    Get an existing candidate by email or create a new one if not found.
    
    Args:
        session: Database session
        email: Candidate's email address
        **candidate_data: Additional candidate data for creation
        
    Returns:
        tuple: (candidate, created) where created is a boolean indicating if the candidate was created
    """
    from sqlalchemy.future import select
    from sqlalchemy import or_
    from .models import Candidate
    
    # Try to find an existing candidate by email
    result = await session.execute(
        select(Candidate).where(
            or_(
                Candidate.email == email,
                Candidate.alternative_emails.contains([email])
            )
        )
    )
    candidate = result.scalars().first()
    
    if candidate:
        return candidate, False
        
    # Create a new candidate if not found
    candidate_data['email'] = email
    candidate = Candidate(**candidate_data)
    session.add(candidate)
    return candidate, True


async def update_candidate_data(session: AsyncSession, candidate_id: str, update_data: dict) -> bool:
    """
    Update candidate data by ID
    
    Args:
        session: Database session
        candidate_id: ID of the candidate to update
        update_data: Dictionary of fields to update
        
    Returns:
        bool: True if update was successful, False if candidate not found
    """
    from .models import Candidate
    from sqlalchemy.future import select
    
    result = await session.execute(
        select(Candidate).where(Candidate.id == candidate_id)
    )
    candidate = result.scalars().first()
    
    if not candidate:
        return False
        
    for key, value in update_data.items():
        if hasattr(candidate, key):
            setattr(candidate, key, value)
            
    return True


async def get_job_listing(session: AsyncSession, job_id: str):
    """
    Get a job listing by ID
    
    Args:
        session: Database session
        job_id: ID of the job listing to retrieve
        
    Returns:
        JobListing or None: The job listing if found, None otherwise
    """
    from .models import JobListing
    from sqlalchemy.future import select
    
    result = await session.execute(
        select(JobListing).where(JobListing.id == job_id)
    )
    return result.scalars().first()


async def create_candidate(session: AsyncSession, candidate_data: dict) -> str:
    """Create a new candidate record"""
    from .models import Candidate

    candidate = Candidate(**candidate_data)
    session.add(candidate)
    await session.flush()  # Get the ID without committing

    return str(candidate.id)


async def get_candidate_by_session(session: AsyncSession, session_id: str):
    """Get candidate by session ID"""
    from .models import Candidate
    from sqlalchemy import select

    stmt = select(Candidate).where(Candidate.session_id == session_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_active_job_listings(session: AsyncSession, limit: int = 100):
    """Get active job listings"""
    from .models import JobListing
    from sqlalchemy import select

    stmt = (
        select(JobListing)
        .where(JobListing.active == True)
        .order_by(JobListing.urgent.desc(), JobListing.posted_date.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def create_application(session: AsyncSession, application_data: dict) -> str:
    """Create a new application record"""
    from .models import Application

    application = Application(**application_data)
    session.add(application)
    await session.flush()

    return str(application.id)


async def get_pending_notifications(session: AsyncSession, limit: int = 100):
    """Get pending notifications for delivery"""
    from .models import Notification
    from sqlalchemy import select, or_
    from datetime import datetime

    now = datetime.utcnow()

    stmt = (
        select(Notification)
        .where(
            or_(
                Notification.delivery_status == 'pending',
                (Notification.delivery_status == 'failed') &
                (Notification.next_retry_at <= now) &
                (Notification.delivery_attempts < Notification.max_retries)
            )
        )
        .order_by(Notification.created_at)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return result.scalars().all()


# Database health monitoring
async def get_connection_pool_status() -> dict:
    """Get connection pool status for monitoring"""
    global engine

    if not engine:
        return {'status': 'not_initialized'}

    pool = engine.pool

    return {
        'status': 'healthy',
        'pool_size': pool.size(),
        'checked_in': pool.checkedin(),
        'checked_out': pool.checkedout(),
        'overflow': pool.overflow(),
        'invalidated': pool.invalidated()
    }