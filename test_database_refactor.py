#!/usr/bin/env python3
"""
Test script to verify the refactored database modules work correctly.
"""

import asyncio
import os
import sys
from loguru import logger

# Set environment variable to use SQLite for testing
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_refactor.db"

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import from the refactored database modules
from app.database.core import (
    init_database,
    close_database,
    get_session,
    test_connection,
    get_connection_pool_status,
    get_database_stats
)

from app.database.candidate_operations import (
    create_candidate,
    get_candidate_by_email
)

from app.database.job_operations import (
    create_job_listing,
    get_active_job_listings
)

from app.database.application_operations import (
    create_application
)

from app.database.notification_operations import (
    record_notification,
    get_pending_notifications
)

from app.database.audit_operations import (
    log_audit_event,
    get_audit_logs
)


async def test_database_modules():
    """Test the refactored database modules."""
    logger.info("Starting database module tests...")
    
    # Initialize database
    logger.info("Initializing database...")
    await init_database()
    
    # Test connection
    logger.info("Testing database connection...")
    connection_ok = await test_connection()
    if not connection_ok:
        logger.error("Database connection test failed!")
        return False
    
    logger.info("Database connection test successful!")
    
    # Get connection pool status
    pool_status = await get_connection_pool_status()
    logger.info(f"Connection pool status: {pool_status}")
    
    # Create test data
    async with get_session() as session:
        # Create a test candidate
        logger.info("Creating test candidate...")
        candidate_id = await create_candidate(
            session,
            email="test@example.com",
            first_name="Test",
            last_name="User",
            phone="+1234567890",
            session_id="test_session"
        )
        logger.info(f"Created candidate with ID: {candidate_id}")
        
        # Retrieve the candidate
        logger.info("Retrieving candidate by email...")
        candidate = await get_candidate_by_email(session, "test@example.com")
        if not candidate:
            logger.error("Failed to retrieve candidate!")
            return False
        
        logger.info(f"Retrieved candidate: {candidate.first_name} {candidate.last_name}")
        
        # Create a job listing
        logger.info("Creating test job listing...")
        job_id = await create_job_listing(
            session,
            title="Test Job",
            description="This is a test job listing",
            company="Test Company",
            location="Remote",
            salary_range="Competitive",
            requirements=["Python", "SQL", "API Development"],
            created_by="admin"
        )
        logger.info(f"Created job listing with ID: {job_id}")
        
        # Get active job listings
        logger.info("Getting active job listings...")
        jobs = await get_active_job_listings(session)
        logger.info(f"Found {len(jobs)} active job listings")
        
        # Create an application
        logger.info("Creating test application...")
        application_id = await create_application(
            session,
            candidate_id=candidate_id,
            job_id=job_id,
            resume_text="Test resume content",
            cover_letter="Test cover letter",
            status="submitted"
        )
        logger.info(f"Created application with ID: {application_id}")
        
        # Record a notification
        logger.info("Recording test notification...")
        notification_id = await record_notification(
            session,
            recipient_id=candidate_id,
            notification_type="email",
            title="Application Received",
            message="Your application has been received",
            status="pending"
        )
        logger.info(f"Created notification with ID: {notification_id}")
        
        # Get pending notifications
        logger.info("Getting pending notifications...")
        notifications = await get_pending_notifications(session)
        logger.info(f"Found {len(notifications)} pending notifications")
        
        # Log an audit event
        logger.info("Logging test audit event...")
        audit_id = await log_audit_event(
            session,
            event_type="user_action",
            user_id="admin",
            target_id=candidate_id,
            target_type="candidate",
            details={"action": "test"}
        )
        logger.info(f"Created audit log with ID: {audit_id}")
        
        # Get audit logs
        logger.info("Getting audit logs...")
        audit_logs = await get_audit_logs(session)
        logger.info(f"Found {len(audit_logs)} audit logs")
    
    # Close database connection
    logger.info("Closing database connection...")
    await close_database()
    
    logger.info("All database module tests completed successfully!")
    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(test_database_modules())
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        sys.exit(1)
