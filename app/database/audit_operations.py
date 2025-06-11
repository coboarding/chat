# app/database/audit_operations.py
"""
Database operations related to audit logging for coBoarding platform
"""

import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_, func, text
from sqlalchemy.orm import joinedload
from loguru import logger

from .models import AuditLog


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
    audit_id = str(uuid.uuid4())
    
    # Create audit log entry
    audit_log = AuditLog(
        id=audit_id,
        event_type=event_type,
        user_id=user_id,
        target_id=target_id,
        target_type=target_type,
        details=details or {},
        ip_address=ip_address,
        user_agent=user_agent,
        timestamp=datetime.utcnow()
    )
    
    session.add(audit_log)
    await session.commit()
    
    logger.debug(f"Logged audit event: {event_type} for user {user_id} on {target_type} {target_id}")
    return audit_id


async def get_audit_logs(
    session: AsyncSession,
    user_id: str = None,
    target_id: str = None,
    target_type: str = None,
    event_type: str = None,
    start_date: datetime = None,
    end_date: datetime = None,
    limit: int = 100,
    offset: int = 0
) -> List[AuditLog]:
    """
    Get audit logs with various filters
    
    Args:
        session: Database session
        user_id: Optional filter by user ID
        target_id: Optional filter by target ID
        target_type: Optional filter by target type
        event_type: Optional filter by event type
        start_date: Optional filter by start date
        end_date: Optional filter by end date
        limit: Maximum number of logs to return
        offset: Number of logs to skip
        
    Returns:
        list: List of AuditLog objects
    """
    # Build query
    query = select(AuditLog)
    
    # Apply filters
    filters = []
    
    if user_id:
        filters.append(AuditLog.user_id == user_id)
    
    if target_id:
        filters.append(AuditLog.target_id == target_id)
    
    if target_type:
        filters.append(AuditLog.target_type == target_type)
    
    if event_type:
        filters.append(AuditLog.event_type == event_type)
    
    if start_date:
        filters.append(AuditLog.timestamp >= start_date)
    
    if end_date:
        filters.append(AuditLog.timestamp <= end_date)
    
    # Apply all filters
    if filters:
        query = query.where(and_(*filters))
    
    # Add sorting and pagination
    query = (
        query
        .order_by(AuditLog.timestamp.desc())
        .limit(limit)
        .offset(offset)
    )
    
    # Execute query
    result = await session.execute(query)
    return result.scalars().all()


async def get_user_activity_summary(
    session: AsyncSession,
    user_id: str,
    days: int = 30
) -> Dict[str, Any]:
    """
    Get a summary of user activity from audit logs
    
    Args:
        session: Database session
        user_id: ID of the user
        days: Number of days to include in summary
        
    Returns:
        dict: Summary of user activity
    """
    # Calculate start date
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Get count of each event type
    query = (
        select(AuditLog.event_type, func.count().label('count'))
        .where(
            and_(
                AuditLog.user_id == user_id,
                AuditLog.timestamp >= start_date
            )
        )
        .group_by(AuditLog.event_type)
    )
    
    result = await session.execute(query)
    event_counts = {row[0]: row[1] for row in result}
    
    # Get most recent activity
    recent_query = (
        select(AuditLog)
        .where(AuditLog.user_id == user_id)
        .order_by(AuditLog.timestamp.desc())
        .limit(5)
    )
    
    recent_result = await session.execute(recent_query)
    recent_activities = recent_result.scalars().all()
    
    # Format recent activities
    formatted_recent = [
        {
            "event_type": activity.event_type,
            "timestamp": activity.timestamp.isoformat() if activity.timestamp else None,
            "target_type": activity.target_type,
            "details": activity.details
        }
        for activity in recent_activities
    ]
    
    # Compile summary
    summary = {
        "user_id": user_id,
        "period_days": days,
        "event_counts": event_counts,
        "total_events": sum(event_counts.values()),
        "recent_activities": formatted_recent
    }
    
    return summary


async def delete_old_audit_logs(
    session: AsyncSession,
    days_old: int = 90
) -> int:
    """
    Delete audit logs older than the specified number of days
    
    Args:
        session: Database session
        days_old: Age threshold in days
        
    Returns:
        int: Number of audit logs deleted
    """
    threshold_date = datetime.utcnow() - timedelta(days=days_old)
    
    # Delete old audit logs
    stmt = (
        delete(AuditLog)
        .where(AuditLog.timestamp < threshold_date)
        .execution_options(synchronize_session="fetch")
    )
    
    result = await session.execute(stmt)
    await session.commit()
    
    deleted_count = result.rowcount
    logger.info(f"Deleted {deleted_count} audit logs older than {days_old} days")
    
    return deleted_count
