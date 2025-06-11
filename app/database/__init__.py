"""
Database package for coBoarding platform.

This module provides database models, connection utilities, and session management
for the coBoarding speed hiring platform.
"""

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

from .connection import (
    init_database,
    close_database,
    get_db_session,
    get_session,
    test_connection,
    create_candidate,
    get_candidate_by_session,
    get_or_create_candidate_by_email,
    update_candidate_data,
    get_job_listing,
    create_application,
    get_application,
    update_application_status,
    record_notification,
    log_audit_event,
    get_pending_notifications,
    get_applications_for_candidate,
    get_applications_for_job_listing,
    get_overdue_applications,
    get_expired_job_listings,
    get_active_job_listings,
    get_candidate_applications,
    get_application_by_session_and_job,
    get_candidate_by_email,
    delete_candidate_data,
    anonymize_candidate_data,
    export_candidate_data
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
    
    # Candidate operations
    'create_candidate',
    'get_candidate_by_session',
    'get_or_create_candidate_by_email',
    'update_candidate_data',
    'get_candidate_by_email',
    'delete_candidate_data',
    'anonymize_candidate_data',
    'export_candidate_data',
    
    # Job listing operations
    'get_job_listing',
    'get_active_job_listings',
    'get_expired_job_listings',
    
    # Application operations
    'create_application',
    'get_application',
    'update_application_status',
    'get_applications_for_candidate',
    'get_applications_for_job_listing',
    'get_overdue_applications',
    'get_candidate_applications',
    'get_application_by_session_and_job',
    
    # Notification operations
    'record_notification',
    'get_pending_notifications',
    
    # Audit logging
    'log_audit_event'
]

# Initialize database on import
init_database()