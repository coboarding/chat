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
from sqlalchemy import text, delete
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


async def create_postgresql_indexes(conn) -> None:
    """Create PostgreSQL-specific indexes."""
    index_statements = [
        """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_candidates_session_expires 
        ON candidates(session_id, expires_at);
        """,
        """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_applications_status_score 
        ON applications(status, match_score DESC);
        """,
        """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_notifications_retry 
        ON notifications(delivery_status, next_retry_at) 
        WHERE delivery_status = 'failed';
        """
    ]
    
    for stmt in index_statements:
        await conn.execute(text(stmt))


async def create_postgresql_functions(conn) -> None:
    """Create PostgreSQL-specific functions."""
    function_statements = [
        # Cleanup expired data function
        """
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
        """,
        
        # Update application count function
        """
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
        """,
        
        # Drop existing trigger if it exists
        """
        DROP TRIGGER IF EXISTS trigger_application_count ON applications;
        """,
        
        # Create trigger
        """
        CREATE TRIGGER trigger_application_count
            AFTER INSERT OR DELETE ON applications
            FOR EACH ROW EXECUTE FUNCTION update_application_count();
        """
    ]
    
    for stmt in function_statements:
        await conn.execute(text(stmt))


async def create_sqlite_indexes(conn) -> None:
    """Create SQLite-specific indexes."""
    # SQLite requires each statement to be executed separately
    index_statements = [
        """
        CREATE INDEX IF NOT EXISTS idx_candidates_session_expires 
        ON candidates(session_id, expires_at);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_applications_status_score 
        ON applications(status, match_score);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_notifications_retry 
        ON notifications(delivery_status, next_retry_at) 
        WHERE delivery_status = 'failed';
        """
    ]
    
    for stmt in index_statements:
        await conn.execute(text(stmt))
    
    logger.info("Created SQLite-specific indexes")
    
    # SQLite doesn't support triggers with the same functionality as PostgreSQL
    # Application count updates will need to be handled in the application code


async def create_tables() -> None:
    """Create all database tables with appropriate indexes for the current database type."""
    global engine
    
    if engine is None:
        raise RuntimeError("Database engine not initialized")
    
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
    
    # Handle SQLite's NullPool which doesn't have the same methods
    from sqlalchemy.pool import NullPool
    if isinstance(pool, NullPool):
        return {
            "status": "active",
            "pool_type": "NullPool",
            "connections": "unknown",
        }
    
    # For regular connection pools
    return {
        "status": "active",
        "pool_type": pool.__class__.__name__,
        "size": pool.size(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "checkedin": pool.checkedin(),
    }


async def get_database_stats() -> dict:
    """Get database statistics for monitoring and diagnostics"""
    global engine
    
    if not engine:
        return {"status": "not_initialized"}
    
    stats = {}
    
    try:
        async with engine.begin() as conn:
            # Get table row counts
            tables_query = """
                SELECT 
                    table_name, 
                    (SELECT count(*) FROM information_schema.columns 
                     WHERE table_name=t.table_name) as column_count,
                    pg_total_relation_size(quote_ident(table_name)) as total_bytes
                FROM information_schema.tables t
                WHERE table_schema = 'public'
                ORDER BY total_bytes DESC;
            """
            
            table_stats = await conn.execute(text(tables_query))
            tables = []
            
            for row in table_stats:
                table_name = row.table_name
                count_query = f"SELECT COUNT(*) as count FROM {table_name}"
                count_result = await conn.execute(text(count_query))
                count = count_result.scalar()
                
                tables.append({
                    "name": table_name,
                    "rows": count,
                    "columns": row.column_count,
                    "size_bytes": row.total_bytes,
                    "size_mb": round(row.total_bytes / (1024 * 1024), 2)
                })
            
            stats["tables"] = tables
            
            # Get database size
            size_query = "SELECT pg_database_size(current_database()) as size;"
            size_result = await conn.execute(text(size_query))
            db_size = size_result.scalar()
            
            stats["database_size_bytes"] = db_size
            stats["database_size_mb"] = round(db_size / (1024 * 1024), 2)
            
            # Get connection stats
            conn_query = """
                SELECT count(*) as active_connections 
                FROM pg_stat_activity 
                WHERE datname = current_database();
            """
            conn_result = await conn.execute(text(conn_query))
            conn_count = conn_result.scalar()
            
            stats["active_connections"] = conn_count
            
            # Add pool stats
            stats["pool"] = await get_connection_pool_status()
            
            return stats
    except Exception as e:
        logger.error(f"Error getting database stats: {e}")
        return {"status": "error", "message": str(e)}


async def run_cleanup() -> dict:
    """Run database cleanup tasks to remove expired data"""
    global engine
    
    if not engine:
        return {"status": "not_initialized"}
    
    results = {}
    
    try:
        async with engine.begin() as conn:
            # Check if we're using PostgreSQL
            if engine.dialect.name == 'postgresql':
                # Use the database function for cleanup
                cleanup_result = await conn.execute(text("SELECT cleanup_expired_data()"))
                deleted_count = cleanup_result.scalar()
                results["expired_records_deleted"] = deleted_count
            else:
                # For other databases, do manual cleanup
                from datetime import datetime
                from .models import Candidate
                
                # Delete expired candidates (cascades to applications and notifications)
                delete_stmt = delete(Candidate).where(Candidate.expires_at < datetime.utcnow())
                delete_result = await conn.execute(delete_stmt)
                results["expired_candidates_deleted"] = delete_result.rowcount
            
            # Vacuum analyze (PostgreSQL only)
            if engine.dialect.name == 'postgresql':
                try:
                    # VACUUM can't run in a transaction, so we need a separate connection
                    # This is a bit hacky but works for PostgreSQL
                    db_url = get_database_url()
                    conn_params = db_url.replace('postgresql+asyncpg://', '')
                    
                    # Extract connection parameters
                    user_pass, host_db = conn_params.split('@')
                    if ':' in user_pass:
                        user, password = user_pass.split(':', 1)
                    else:
                        user, password = user_pass, ''
                        
                    host_port, db = host_db.split('/', 1)
                    if ':' in host_port:
                        host, port = host_port.split(':', 1)
                    else:
                        host, port = host_port, '5432'
                    
                    # Connect directly with asyncpg
                    conn = await asyncpg.connect(
                        user=user,
                        password=password,
                        database=db,
                        host=host,
                        port=port
                    )
                    
                    # Run vacuum analyze
                    await conn.execute('VACUUM ANALYZE')
                    await conn.close()
                    
                    results["vacuum_analyze"] = "completed"
                except Exception as e:
                    logger.warning(f"VACUUM ANALYZE failed: {e}")
                    results["vacuum_analyze"] = f"failed: {e}"
        
        return {"status": "success", "results": results}
    except Exception as e:
        logger.error(f"Error running database cleanup: {e}")
        return {"status": "error", "message": str(e)}
