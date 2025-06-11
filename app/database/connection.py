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
    
    # Connection pool configuration
    pool_class = None  # Default to NullPool for SQLite
    connect_args: dict = {}
    
    if 'sqlite' in database_url:
        # SQLite specific configuration
        connect_args = {"check_same_thread": False}  # Required for SQLite in async mode
    else:
        # PostgreSQL specific configuration
        pool_class = NullPool  # Use NullPool for PostgreSQL with asyncpg
        connect_args = {
            "server_settings": {
                "jit": "off",  # Disable JIT for faster query planning
                "application_name": "coboarding_api",
            },
            "command_timeout": 30,  # 30 second query timeout
            "statement_cache_size": 0,  # Disable prepared statement cache
        }
    
    # Common engine arguments
    engine_args = {
        'echo': os.getenv('ENVIRONMENT') == 'development',  # Log SQL queries in dev
        'future': True,  # Use SQLAlchemy 2.0 style
        'connect_args': connect_args,
    }
    
    # Add pool configuration if needed
    if pool_class:
        engine_args['poolclass'] = pool_class
    
    return create_async_engine(database_url, **engine_args)


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
    """Create all database tables with appropriate indexes for the current database type."""
    global engine

    if not engine:
        raise RuntimeError("Database engine not initialized. Call init_database() first.")

    logger.info("Creating database tables...")
    
    try:
        async with engine.begin() as conn:
            # Create tables from SQLAlchemy models
            await conn.run_sync(Base.metadata.create_all)
            
            # Get database dialect
            dialect = engine.dialect.name
            logger.info(f"Using database dialect: {dialect}")

            if dialect == 'postgresql':
                # PostgreSQL specific indexes and functions
                await create_postgresql_indexes(conn)
                await create_postgresql_functions(conn)
            elif dialect == 'sqlite':
                # SQLite specific indexes (no CONCURRENTLY support)
                await create_sqlite_indexes(conn)
            else:
                logger.warning(f"Unsupported database dialect: {dialect}. Only basic tables will be created.")

        logger.info("✅ Database tables created successfully")

    except Exception as e:
        logger.error(f"❌ Table creation failed: {e}")
        raise


async def create_postgresql_indexes(conn) -> None:
    """Create PostgreSQL-specific indexes."""
    await conn.execute(text("""
        -- Create additional indexes for performance
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_candidates_session_expires 
        ON candidates(session_id, expires_at);

        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_applications_status_score 
        ON applications(status, match_score DESC);

        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_notifications_retry 
        ON notifications(delivery_status, next_retry_at) 
        WHERE delivery_status = 'failed';
    """))


async def create_postgresql_functions(conn) -> None:
    """Create PostgreSQL-specific functions."""
    await conn.execute(text("""
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


async def create_sqlite_indexes(conn) -> None:
    """Create SQLite-specific indexes."""
    await conn.execute(text("""
        -- Create additional indexes for performance
        CREATE INDEX IF NOT EXISTS idx_candidates_session_expires 
        ON candidates(session_id, expires_at);

        CREATE INDEX IF NOT EXISTS idx_applications_status_score 
        ON applications(status, match_score);

        CREATE INDEX IF NOT EXISTS idx_notifications_retry 
        ON notifications(delivery_status, next_retry_at) 
        WHERE delivery_status = 'failed';

        -- SQLite doesn't support triggers with the same functionality as PostgreSQL
        -- Application count updates will need to be handled in the application code
    """))
    logger.info("Created SQLite-specific indexes")


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


async def log_audit_event(
    session: AsyncSession,
    event_type: str,
    user_id: str = None,
    target_id: str = None,
    target_type: str = None,
    details: dict = None,
    ip_address: str = None,
    user_agent: str = None
) -> str:
    """
    Log an audit event to the database
    
    Args:
        session: Database session
        event_type: Type of event (e.g., 'user_login', 'data_access', 'data_modification')
        user_id: ID of the user who performed the action (if any)
        target_id: ID of the target entity (if any)
        target_type: Type of the target entity (e.g., 'user', 'candidate', 'application')
        details: Additional details about the event
        ip_address: IP address of the client
        user_agent: User agent string of the client
        
    Returns:
        str: ID of the created audit log entry
    """
    from .models import AuditLog
    from datetime import datetime
    
    audit_entry = AuditLog(
        event_type=event_type,
        user_id=user_id,
        target_id=target_id,
        target_type=target_type,
        details=details or {},
        ip_address=ip_address,
        user_agent=user_agent,
        created_at=datetime.utcnow()
    )
    
    session.add(audit_entry)
    await session.flush()
    
    return str(audit_entry.id)


async def record_notification(
    session: AsyncSession,
    recipient_id: str,
    notification_type: str,
    title: str,
    message: str,
    status: str = 'pending',
    metadata: dict = None
) -> str:
    """
    Record a notification in the database
    
    Args:
        session: Database session
        recipient_id: ID of the recipient user
        notification_type: Type of notification (email, sms, push, etc.)
        title: Notification title
        message: Notification message content
        status: Initial status (default: 'pending')
        metadata: Additional metadata as a dictionary
        
    Returns:
        str: ID of the created notification
    """
    from .models import Notification
    from datetime import datetime
    
    notification = Notification(
        recipient_id=recipient_id,
        notification_type=notification_type,
        title=title,
        message=message,
        status=status,
        metadata=metadata or {},
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    session.add(notification)
    await session.flush()
    
    return str(notification.id)


async def update_application_status(session: AsyncSession, application_id: str, new_status: str, status_message: str = None) -> bool:
    """
    Update the status of an application
    
    Args:
        session: Database session
        application_id: ID of the application to update
        new_status: New status to set
        status_message: Optional message about the status change
        
    Returns:
        bool: True if update was successful, False if application not found
    """
    from .models import Application, ApplicationStatus
    from sqlalchemy.future import select
    from datetime import datetime
    
    result = await session.execute(
        select(Application).where(Application.id == application_id)
    )
    application = result.scalars().first()
    
    if not application:
        return False
        
    application.status = ApplicationStatus(new_status)
    application.status_message = status_message
    application.updated_at = datetime.utcnow()
    
    return True


async def get_application(session: AsyncSession, application_id: str):
    """
    Get an application by ID
    
    Args:
        session: Database session
        application_id: ID of the application to retrieve
        
    Returns:
        Application or None: The application if found, None otherwise
    """
    from .models import Application
    from sqlalchemy.future import select
    
    result = await session.execute(
        select(Application).where(Application.id == application_id)
    )
    return result.scalars().first()


async def get_expired_job_listings(
    session: AsyncSession,
    limit: int = 100,
    offset: int = 0,
    include_closed: bool = False
) -> list:
    """
    Get job listings that have passed their deadline
    
    Args:
        session: Database session
        limit: Maximum number of job listings to return
        offset: Number of job listings to skip
        include_closed: Whether to include already closed/expired listings
        
    Returns:
        list: List of expired JobListing objects
    """
    from .models import JobListing
    from sqlalchemy.future import select
    from sqlalchemy import and_, or_
    from datetime import datetime
    
    # Build the base query
    query = select(JobListing).where(
        and_(
            JobListing.deadline.is_not(None),
            JobListing.deadline < datetime.utcnow()
        )
    )
    
    # Optionally filter out already closed/expired listings
    if not include_closed:
        query = query.where(
            or_(
                JobListing.status == 'active',
                JobListing.status == 'published',
                JobListing.status.is_(None)
            )
        )
    
    # Order by deadline (most recently expired first)
    query = query.order_by(JobListing.deadline.desc())
    
    # Apply pagination
    query = query.limit(limit).offset(offset)
    
    result = await session.execute(query)
    return result.scalars().all()


async def get_overdue_applications(
    session: AsyncSession,
    days_overdue: int = 7,
    limit: int = 100,
    offset: int = 0
) -> list:
    """
    Get applications that are overdue by a specified number of days
    
    Args:
        session: Database session
        days_overdue: Number of days after which an application is considered overdue
        limit: Maximum number of applications to return
        offset: Number of applications to skip
        
    Returns:
        list: List of overdue Application objects with related job and candidate info
    """
    from .models import Application, JobListing, Candidate
    from sqlalchemy.future import select
    from sqlalchemy import and_, or_, desc
    from datetime import datetime, timedelta
    
    # Calculate the cutoff date
    cutoff_date = datetime.utcnow() - timedelta(days=days_overdue)
    
    # Build the query to find overdue applications
    query = select(Application).join(
        JobListing, Application.job_listing_id == JobListing.id
    ).join(
        Candidate, Application.candidate_id == Candidate.id
    ).where(
        and_(
            Application.status.not_in(['rejected', 'withdrawn', 'hired']),
            Application.updated_at <= cutoff_date,
            or_(
                JobListing.deadline.is_(None),
                JobListing.deadline >= datetime.utcnow()
            )
        )
    ).order_by(desc(Application.updated_at))
    
    # Apply pagination
    query = query.limit(limit).offset(offset)
    
    result = await session.execute(query)
    return result.scalars().all()


async def get_applications_for_job_listing(
    session: AsyncSession,
    job_listing_id: str,
    limit: int = 100,
    offset: int = 0,
    status: str = None,
    sort_by: str = 'created_at',
    sort_order: str = 'desc'
) -> list:
    """
    Get all applications for a specific job listing
    
    Args:
        session: Database session
        job_listing_id: ID of the job listing
        limit: Maximum number of applications to return
        offset: Number of applications to skip
        status: Optional status to filter applications by
        sort_by: Field to sort by (default: 'created_at')
        sort_order: Sort order ('asc' or 'desc')
        
    Returns:
        list: List of Application objects with joined candidate information
    """
    from .models import Application, Candidate
    from sqlalchemy.future import select
    from sqlalchemy import and_, desc, asc
    
    # Start building the query with a join to get candidate details
    query = select(Application).join(
        Candidate, Application.candidate_id == Candidate.id
    ).where(Application.job_listing_id == job_listing_id)
    
    # Apply status filter if provided
    if status:
        query = query.where(Application.status == status)
    
    # Apply sorting
    sort_field = getattr(Application, sort_by, Application.created_at)
    if sort_order.lower() == 'asc':
        query = query.order_by(asc(sort_field))
    else:
        query = query.order_by(desc(sort_field))
    
    # Apply pagination
    query = query.limit(limit).offset(offset)
    
    result = await session.execute(query)
    return result.scalars().all()


async def get_applications_for_candidate(
    session: AsyncSession, 
    candidate_id: str,
    limit: int = 100,
    offset: int = 0,
    status: str = None
) -> list:
    """
    Get all applications for a specific candidate
    
    Args:
        session: Database session
        candidate_id: ID of the candidate
        limit: Maximum number of applications to return
        offset: Number of applications to skip
        status: Optional status to filter applications by
        
    Returns:
        list: List of Application objects
    """
    from .models import Application
    from sqlalchemy.future import select
    from sqlalchemy import and_
    
    query = select(Application).where(Application.candidate_id == candidate_id)
    
    if status:
        query = query.where(Application.status == status)
        
    query = query.order_by(Application.created_at.desc())
    query = query.limit(limit).offset(offset)
    
    result = await session.execute(query)
    return result.scalars().all()


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


async def get_overdue_applications(session: AsyncSession, days_overdue: int = 1, limit: int = 100):
    """
    Retrieve applications that are overdue for a response
    
    Args:
        session: Database session
        days_overdue: Number of days after which an application is considered overdue
        limit: Maximum number of applications to return
        
    Returns:
        list: List of overdue applications
    """
    from sqlalchemy import select, and_
    from datetime import datetime, timedelta
    from .models import Application, JobListing, Candidate
    
    try:
        # Calculate the cutoff date
        cutoff_date = datetime.utcnow() - timedelta(days=days_overdue)
        
        # Build the query
        stmt = (
            select(Application)
            .join(JobListing, Application.job_listing_id == JobListing.id)
            .join(Candidate, Application.candidate_id == Candidate.id)
            .where(
                and_(
                    Application.status == 'submitted',
                    Application.created_at < cutoff_date,
                    Application.responded_at.is_(None)
                )
            )
            .order_by(Application.created_at.asc())
            .limit(limit)
        )
        
        result = await session.execute(stmt)
        return result.scalars().all()
        
    except Exception as e:
        logger.error(f"Error fetching overdue applications: {str(e)}")
        raise


async def get_expired_job_listings(session: AsyncSession, limit: int = 100):
    """
    Retrieve job listings that have passed their deadline
    
    Args:
        session: Database session
        limit: Maximum number of job listings to return
        
    Returns:
        list: List of expired job listings
    """
    from sqlalchemy import select, and_
    from datetime import datetime
    from .models import JobListing
    
    try:
        current_time = datetime.utcnow()
        
        # Build the query
        stmt = (
            select(JobListing)
            .where(
                and_(
                    JobListing.deadline.isnot(None),
                    JobListing.deadline < current_time,
                    JobListing.status == 'active'
                )
            )
            .order_by(JobListing.deadline.desc())
            .limit(limit)
        )
        
        result = await session.execute(stmt)
        return result.scalars().all()
        
    except Exception as e:
        logger.error(f"Error fetching expired job listings: {str(e)}")
        raise


async def get_candidate_applications(session: AsyncSession, candidate_id: str, limit: int = 100, offset: int = 0):
    """
    Get all applications for a specific candidate with pagination
    
    Args:
        session: Database session
        candidate_id: ID of the candidate
        limit: Maximum number of applications to return
        offset: Number of applications to skip
        
    Returns:
        list: List of applications with job listing details
    """
    from sqlalchemy import select
    from .models import Application, JobListing
    
    try:
        stmt = (
            select(Application, JobListing)
            .join(JobListing, Application.job_listing_id == JobListing.id)
            .where(Application.candidate_id == candidate_id)
            .order_by(Application.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        
        result = await session.execute(stmt)
        return [
            {
                'application': app,
                'job_listing': job
            }
            for app, job in result.all()
        ]
        
    except Exception as e:
        logger.error(f"Error fetching applications for candidate {candidate_id}: {str(e)}")
        raise


async def get_application_by_session_and_job(session: AsyncSession, session_id: str, job_listing_id: str):
    """
    Get an application by session ID and job listing ID
    
    Args:
        session: Database session
        session_id: Session ID of the candidate
        job_listing_id: ID of the job listing
        
    Returns:
        Application or None: The application if found, None otherwise
    """
    from sqlalchemy import select, and_
    from .models import Application, Candidate
    
    try:
        # First, get the candidate ID from the session
        stmt = (
            select(Application)
            .join(Candidate, Application.candidate_id == Candidate.id)
            .where(
                and_(
                    Candidate.session_id == session_id,
                    Application.job_listing_id == job_listing_id
                )
            )
        )
        
        result = await session.execute(stmt)
        return result.scalars().first()
        
    except Exception as e:
        logger.error(
            f"Error fetching application for session {session_id} and job {job_listing_id}: {str(e)}"
        )
        raise


async def anonymize_candidate_data(
    session: AsyncSession, 
    candidate_id: str,
    anonymization_fields: dict = None
) -> bool:
    """
    Anonymize candidate data for GDPR compliance
    
    Args:
        session: Database session
        candidate_id: ID of the candidate to anonymize
        anonymization_fields: Dictionary of fields to anonymize and their values
        
    Returns:
        bool: True if anonymization was successful, False otherwise
    """
    from .models import Candidate
    from sqlalchemy import update
    import uuid
    
    # Default fields to anonymize if not provided
    if anonymization_fields is None:
        anonymization_fields = {
            'first_name': 'Anonymized',
            'last_name': 'User',
            'email': f'anonymous_{uuid.uuid4().hex[:12]}@example.com',
            'phone': None,
            'address': None,
            'city': None,
            'country': None,
            'postal_code': None,
            'linkedin_url': None,
            'github_url': None,
            'website': None,
            'summary': 'Data anonymized for privacy',
            'is_anonymized': True,
            'anonymized_at': datetime.utcnow()
        }
    
    try:
        # Update candidate with anonymized data
        stmt = (
            update(Candidate)
            .where(Candidate.id == candidate_id)
            .values(**anonymization_fields)
        )
        
        result = await session.execute(stmt)
        await session.commit()
        
        # Log the anonymization
        await log_audit_event(
            session=session,
            event_type='candidate_anonymized',
            entity_type='candidate',
            entity_id=candidate_id,
            details={'fields_anonymized': list(anonymization_fields.keys())},
            user_id='system',
            user_type='system'
        )
        
        return result.rowcount > 0
        
    except Exception as e:
        await session.rollback()
        logger.error(f"Error anonymizing candidate {candidate_id}: {str(e)}")
        raise


async def get_candidate_by_email(session: AsyncSession, email: str):
    """
    Get a candidate by their email address
    
    Args:
        session: Database session
        email: Email address of the candidate
        
    Returns:
        Candidate or None: The candidate if found, None otherwise
    """
    from sqlalchemy import select
    from .models import Candidate
    
    try:
        stmt = select(Candidate).where(Candidate.email == email)
        result = await session.execute(stmt)
        return result.scalars().first()
        
    except Exception as e:
        logger.error(f"Error fetching candidate by email {email}: {str(e)}")
        raise


async def delete_candidate_data(session: AsyncSession, candidate_id: str, anonymize: bool = True):
    """
    Delete or anonymize a candidate's personal data for GDPR compliance
    
    Args:
        session: Database session
        candidate_id: ID of the candidate
        anonymize: If True, anonymize the data instead of deleting it
        
    Returns:
        bool: True if successful, False otherwise
    """
    from datetime import datetime
    from sqlalchemy import update, and_
    from .models import Candidate, Application, AuditLog
    
    try:
        # Create audit log entry before deletion
        await log_audit_event(
            session=session,
            event_type='data_deletion',
            target_id=candidate_id,
            target_type='candidate',
            details={'anonymize': anonymize},
            ip_address='system',
            user_agent='coboarding/1.0'
        )
        
        if anonymize:
            # Use the anonymize function
            return await anonymize_candidate_data(session, candidate_id)
        else:
            # Hard delete the candidate and related data
            # Note: This will cascade to related records if foreign key constraints are set up that way
            stmt = select(Candidate).where(Candidate.id == candidate_id)
            result = await session.execute(stmt)
            candidate = result.scalars().first()
            
            if candidate:
                await session.delete(candidate)
        
        await session.commit()
        return True
        
    except Exception as e:
        await session.rollback()
        logger.error(f"Error deleting candidate data for {candidate_id}: {str(e)}")
        raise


async def anonymize_candidate_data(session: AsyncSession, candidate_id: str):
    """
    Anonymize a candidate's personal data for GDPR compliance
    
    Args:
        session: Database session
        candidate_id: ID of the candidate to anonymize
        
    Returns:
        bool: True if successful, False otherwise
    """
    from datetime import datetime
    from sqlalchemy import update
    from .models import Candidate
    
    try:
        # Anonymize personal data
        stmt = (
            update(Candidate)
            .where(Candidate.id == candidate_id)
            .values(
                email=f'anonymized-{candidate_id}@deleted.local',
                first_name='Anonymous',
                last_name='User',
                phone_number=None,
                address=None,
                date_of_birth=None,
                profile_picture=None,
                resume_path=None,
                is_active=False,
                deleted_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
        )
        
        result = await session.execute(stmt)
        await session.commit()
        
        # Check if any rows were updated
        return result.rowcount > 0
        
    except Exception as e:
        await session.rollback()
        logger.error(f"Error anonymizing candidate data for {candidate_id}: {str(e)}")
        raise


async def export_candidate_data(session: AsyncSession, candidate_id: str) -> dict:
    """
    Export all data related to a candidate in a structured format for GDPR compliance.
    
    Args:
        session: Database session
        candidate_id: ID of the candidate whose data to export
        
    Returns:
        dict: A dictionary containing all the candidate's data in a structured format
    """
    from sqlalchemy import select
    from .models import (
        Candidate, Application, Notification, AuditLog
    )
    from datetime import datetime
    import json
    
    try:
        # Get candidate data
        stmt = select(Candidate).where(Candidate.id == candidate_id)
        result = await session.execute(stmt)
        candidate = result.scalars().first()
        
        if not candidate:
            return {"error": "Candidate not found"}
        
        # Get candidate's applications
        app_stmt = (
            select(Application)
            .where(Application.candidate_id == candidate_id)
            .order_by(Application.created_at.desc())
        )
        app_result = await session.execute(app_stmt)
        applications = app_result.scalars().all()
        
        # Get candidate's notifications
        notif_stmt = (
            select(Notification)
            .where(Notification.recipient_id == candidate_id)
            .order_by(Notification.created_at.desc())
        )
        notif_result = await session.execute(notif_stmt)
        notifications = notif_result.scalars().all()
        
        # Get audit logs related to the candidate
        audit_stmt = (
            select(AuditLog)
            .where(AuditLog.target_id == candidate_id)
            .order_by(AuditLog.created_at.desc())
        )
        audit_result = await session.execute(audit_stmt)
        audit_logs = audit_result.scalars().all()
        
        # Create the export data structure
        export_data = {
            "exported_at": datetime.utcnow().isoformat(),
            "candidate": {
                "id": str(candidate.id),
                "email": candidate.email,
                "first_name": candidate.first_name,
                "last_name": candidate.last_name,
                "phone_number": candidate.phone_number,
                "created_at": candidate.created_at.isoformat() if candidate.created_at else None,
                "updated_at": candidate.updated_at.isoformat() if candidate.updated_at else None,
                "last_login_at": candidate.last_login_at.isoformat() if candidate.last_login_at else None,
                "is_active": candidate.is_active,
                "metadata": candidate.metadata or {}
            },
            "applications": [
                {
                    "id": str(app.id),
                    "job_listing_id": str(app.job_listing_id),
                    "status": app.status,
                    "created_at": app.created_at.isoformat(),
                    "updated_at": app.updated_at.isoformat() if app.updated_at else None,
                    "metadata": app.metadata or {}
                }
                for app in applications
            ],
            "notifications": [
                {
                    "id": str(notif.id),
                    "type": notif.notification_type,
                    "title": notif.title,
                    "message": notif.message,
                    "status": notif.status,
                    "created_at": notif.created_at.isoformat(),
                    "read_at": notif.read_at.isoformat() if notif.read_at else None,
                    "metadata": notif.metadata or {}
                }
                for notif in notifications
            ],
            "audit_logs": [
                {
                    "id": str(log.id),
                    "event_type": log.event_type,
                    "details": log.details or {},
                    "ip_address": log.ip_address,
                    "user_agent": log.user_agent,
                    "created_at": log.created_at.isoformat()
                }
                for log in audit_logs
            ]
        }
        
        return export_data
        
    except Exception as e:
        logger.error(f"Error exporting data for candidate {candidate_id}: {str(e)}")
        raise


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