# app/database/connection.py
"""
Database connection and session management for coBoarding platform
Handles PostgreSQL connections with async support and connection pooling

NOTE: This file is maintained for backward compatibility.
New code should import directly from the specific modules:
- core.py
- candidate_operations.py
- application_operations.py
- job_operations.py
- notification_operations.py
- audit_operations.py
"""

# Import core database functionality
from .core import (
    get_database_url,
    create_engine,
    init_database,
    create_tables,
    close_database,
    get_db_session,
    get_session,
    test_connection,
    execute_raw_sql,
    get_database_stats,
    run_cleanup,
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

# For backward compatibility, re-export everything
__all__ = [
    # Core database functionality
    'get_database_url',
    'create_engine',
    'init_database',
    'create_tables',
    'close_database',
    'get_db_session',
    'get_session',
    'test_connection',
    'execute_raw_sql',
    'get_database_stats',
    'run_cleanup',
    'get_connection_pool_status',
    
    # Candidate operations
    'get_or_create_candidate_by_email',
    'update_candidate_data',
    'create_candidate',
    'get_candidate_by_session',
    'get_candidate_by_email',
    'delete_candidate_data',
    'anonymize_candidate_data',
    'export_candidate_data',
    'get_candidate_applications',
    
    # Application operations
    'create_application',
    'get_application',
    'update_application_status',
    'get_applications_for_job_listing',
    'get_applications_for_candidate',
    'get_application_by_session_and_job',
    'get_overdue_applications',
    
    # Job listing operations
    'get_job_listing',
    'get_active_job_listings',
    'get_expired_job_listings',
    'create_job_listing',
    'update_job_listing',
    'deactivate_job_listing',
    'search_job_listings',
    
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
    'delete_old_audit_logs'
]
