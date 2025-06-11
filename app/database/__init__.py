"""
Database package for coBoarding platform.

This module provides database models, connection utilities, and session management
for the coBoarding speed hiring platform.
"""

# Import models
from .models import (
    Base,
    Candidate,
    JobListing,
    Application,
    Notification,
    AuditLog,
    TimestampMixin,
    UUIDMixin
)

# Import core database functionality
from .core import (
    init_database,
    close_database,
    get_db_session,
    get_session,
    test_connection,
    execute_raw_sql,
    get_connection_pool_status
)

# Import candidate operations
from .candidate_operations import (
    get_or_create_candidate_by_email,
    update_candidate_data,
    create_candidate,
    get_candidate_by_session,
    get_candidate_by_email,
    delete_candidate_data,
    anonymize_candidate_data,
    export_candidate_data,
    get_candidate_applications
)

# Import application operations
from .application_operations import (
    create_application,
    get_application,
    update_application_status,
    get_applications_for_job_listing,
    get_applications_for_candidate,
    get_application_by_session_and_job,
    get_overdue_applications
)

# Import job listing operations
from .job_operations import (
    get_job_listing,
    get_active_job_listings,
    get_expired_job_listings,
    create_job_listing,
    update_job_listing,
    deactivate_job_listing,
    search_job_listings
)

# Import notification operations
from .notification_operations import (
    record_notification,
    update_notification_status,
    get_pending_notifications,
    get_notifications_for_recipient,
    delete_old_notifications
)

# Import audit operations
from .audit_operations import (
    log_audit_event,
    get_audit_logs,
    get_user_activity_summary,
    delete_old_audit_logs
)

__all__ = [
    # Models
    'Base',
    'Candidate',
    'JobListing',
    'Application',
    'Notification',
    'AuditLog',
    'TimestampMixin',
    'UUIDMixin',
    
    # Connection and session management
    'init_database',
    'close_database',
    'get_db_session',
    'get_session',
    'test_connection',
    'execute_raw_sql',
    'get_connection_pool_status',
    
    # Candidate operations
    'create_candidate',
    'get_candidate_by_session',
    'get_or_create_candidate_by_email',
    'update_candidate_data',
    'get_candidate_by_email',
    'delete_candidate_data',
    'anonymize_candidate_data',
    'export_candidate_data',
    'get_candidate_applications',
    
    # Job listing operations
    'get_job_listing',
    'get_active_job_listings',
    'get_expired_job_listings',
    'create_job_listing',
    'update_job_listing',
    'deactivate_job_listing',
    'search_job_listings',
    
    # Application operations
    'create_application',
    'get_application',
    'update_application_status',
    'get_applications_for_job_listing',
    'get_applications_for_candidate',
    'get_application_by_session_and_job',
    'get_overdue_applications',
    
    # Notification operations
    'record_notification',
    'update_notification_status',
    'get_pending_notifications',
    'get_notifications_for_recipient',
    'delete_old_notifications',
    
    # Audit operations
    'log_audit_event',
    'get_audit_logs',
    'get_user_activity_summary',
    'delete_old_audit_logs',
    
    # Notification operations
    'record_notification',
    'get_pending_notifications',
    
    # Audit logging
    'log_audit_event'
]

# Initialize database on first use
_db_initialized = False

async def ensure_db_initialized():
    """Ensure the database is initialized when needed"""
    global _db_initialized
    if not _db_initialized:
        from .connection import init_database
        await init_database()
        _db_initialized = True

# Initialize database on import if running in a sync context
import asyncio
import os

if os.environ.get("PYTEST_RUN_CONFIG") != "true":  # Skip during tests
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If there's an event loop running, create a task
            loop.create_task(ensure_db_initialized())
        else:
            # Otherwise, run it directly
            loop.run_until_complete(ensure_db_initialized())
    except RuntimeError:
        # No event loop, will initialize on first use
        pass