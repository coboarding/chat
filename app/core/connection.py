"""
Core database connection and session management for the coBoarding platform.

This module provides a simplified interface to the database connection
functionality from app.database.connection.
"""
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import (
    init_database as db_init_database,
    close_database as db_close_database,
    get_db_session as db_get_db_session,
    get_session as db_get_session,
    test_connection as db_test_connection,
    create_candidate as db_create_candidate,
    get_candidate_by_session as db_get_candidate_by_session,
    get_or_create_candidate_by_email as db_get_or_create_candidate_by_email,
    update_candidate_data as db_update_candidate_data,
    get_job_listing as db_get_job_listing,
    create_application as db_create_application,
    get_application as db_get_application,
    get_applications_for_job_listing as db_get_applications_for_job_listing,
    get_applications_for_candidate as db_get_applications_for_candidate,
    get_active_job_listings as db_get_active_job_listings,
    get_pending_notifications as db_get_pending_notifications,
    log_audit_event as db_log_audit_event,
    record_notification as db_record_notification,
    update_application_status as db_update_application_status,
    get_overdue_applications as db_get_overdue_applications,
    get_expired_job_listings as db_get_expired_job_listings,
    get_candidate_applications as db_get_candidate_applications,
    get_application_by_session_and_job as db_get_application_by_session_and_job,
    delete_candidate_data as db_delete_candidate_data,
    anonymize_candidate_data as db_anonymize_candidate_data,
    export_candidate_data as db_export_candidate_data,
)


# Re-export all the database functions with their original names
init_database = db_init_database
close_database = db_close_database
get_db_session = db_get_db_session
get_session = db_get_session
test_connection = db_test_connection
create_candidate = db_create_candidate
get_candidate_by_session = db_get_candidate_by_session
get_or_create_candidate_by_email = db_get_or_create_candidate_by_email
update_candidate_data = db_update_candidate_data
get_job_listing = db_get_job_listing
create_application = db_create_application
get_application = db_get_application
get_applications_for_job_listing = db_get_applications_for_job_listing
get_applications_for_candidate = db_get_applications_for_candidate
get_active_job_listings = db_get_active_job_listings
get_pending_notifications = db_get_pending_notifications
log_audit_event = db_log_audit_event
record_notification = db_record_notification
update_application_status = db_update_application_status
get_overdue_applications = db_get_overdue_applications
get_expired_job_listings = db_get_expired_job_listings
get_candidate_applications = db_get_candidate_applications
get_application_by_session_and_job = db_get_application_by_session_and_job
delete_candidate_data = db_delete_candidate_data
anonymize_candidate_data = db_anonymize_candidate_data
export_candidate_data = db_export_candidate_data


@asynccontextmanager
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for FastAPI that provides a database session.
    
    Yields:
        AsyncSession: A database session
    """
    async with get_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


__all__ = [
    'init_database',
    'close_database',
    'get_db_session',
    'get_session',
    'get_db',
    'test_connection',
    'create_candidate',
    'get_candidate_by_session',
    'get_or_create_candidate_by_email',
    'update_candidate_data',
    'get_job_listing',
    'create_application',
    'get_application',
    'get_applications_for_job_listing',
    'get_applications_for_candidate',
    'get_active_job_listings',
    'get_pending_notifications',
    'log_audit_event',
    'record_notification',
    'update_application_status',
    'get_overdue_applications',
    'get_expired_job_listings',
    'get_candidate_applications',
    'get_application_by_session_and_job',
    'delete_candidate_data',
    'anonymize_candidate_data',
    'export_candidate_data',
]
