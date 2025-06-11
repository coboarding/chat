# app/database/notification_operations.py
"""
Database operations related to notifications for coBoarding platform
"""

import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_, func, text
from sqlalchemy.orm import joinedload
from loguru import logger

from .models import Notification, Candidate


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
    notification_id = str(uuid.uuid4())
    
    # Create notification
    notification = Notification(
        id=notification_id,
        recipient_id=recipient_id,
        notification_type=notification_type,
        title=title,
        message=message,
        delivery_status=status,
        metadata=metadata or {},
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    session.add(notification)
    await session.commit()
    
    logger.info(f"Recorded {notification_type} notification {notification_id} for recipient {recipient_id}")
    return notification_id


async def update_notification_status(
    session: AsyncSession,
    notification_id: str,
    status: str,
    error_message: str = None
) -> bool:
    """
    Update the status of a notification
    
    Args:
        session: Database session
        notification_id: ID of the notification to update
        status: New status ('delivered', 'failed', etc.)
        error_message: Optional error message if status is 'failed'
        
    Returns:
        bool: True if update was successful, False if notification not found
    """
    # Prepare update data
    update_data = {
        "delivery_status": status,
        "updated_at": datetime.utcnow()
    }
    
    # Add sent_at timestamp if delivered
    if status == 'delivered':
        update_data["sent_at"] = datetime.utcnow()
    
    # Add error message and retry info if failed
    if status == 'failed':
        update_data["error_message"] = error_message
        update_data["retry_count"] = Notification.retry_count + 1
        update_data["next_retry_at"] = datetime.utcnow() + timedelta(
            minutes=min(60, 5 * 2 ** min(8, Notification.retry_count))
        )
    
    # Update notification
    stmt = (
        update(Notification)
        .where(Notification.id == notification_id)
        .values(**update_data)
        .execution_options(synchronize_session="fetch")
    )
    
    result = await session.execute(stmt)
    await session.commit()
    
    if result.rowcount > 0:
        logger.info(f"Updated notification {notification_id} status to {status}")
        return True
    else:
        logger.warning(f"Notification not found for status update: {notification_id}")
        return False


async def get_pending_notifications(
    session: AsyncSession, 
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Get pending notifications for delivery
    
    Args:
        session: Database session
        limit: Maximum number of notifications to return
        
    Returns:
        list: List of pending notifications with recipient info
    """
    now = datetime.utcnow()
    
    # Get notifications that are pending or failed but ready for retry
    query = (
        select(Notification)
        .options(joinedload(Notification.recipient))
        .where(
            or_(
                Notification.delivery_status == 'pending',
                and_(
                    Notification.delivery_status == 'failed',
                    Notification.next_retry_at <= now,
                    Notification.retry_count < 5  # Max retry limit
                )
            )
        )
        .order_by(Notification.created_at.asc())
        .limit(limit)
    )
    
    result = await session.execute(query)
    notifications = result.scalars().all()
    
    # Format results
    formatted_notifications = []
    for notif in notifications:
        recipient = notif.recipient
        
        formatted_notifications.append({
            "id": notif.id,
            "type": notif.notification_type,
            "title": notif.title,
            "message": notif.message,
            "status": notif.delivery_status,
            "created_at": notif.created_at.isoformat() if notif.created_at else None,
            "retry_count": notif.retry_count,
            "recipient": {
                "id": recipient.id if recipient else None,
                "email": recipient.email if recipient else None,
                "name": f"{recipient.first_name} {recipient.last_name}" if recipient else "Unknown"
            },
            "metadata": notif.metadata
        })
    
    return formatted_notifications


async def get_notifications_for_recipient(
    session: AsyncSession,
    recipient_id: str,
    limit: int = 100,
    offset: int = 0,
    status: str = None
) -> List[Notification]:
    """
    Get notifications for a specific recipient
    
    Args:
        session: Database session
        recipient_id: ID of the recipient
        limit: Maximum number of notifications to return
        offset: Number of notifications to skip
        status: Optional status to filter notifications by
        
    Returns:
        list: List of Notification objects
    """
    # Build query
    query = select(Notification).where(Notification.recipient_id == recipient_id)
    
    # Add status filter if provided
    if status:
        query = query.where(Notification.delivery_status == status)
    
    # Add sorting and pagination
    query = (
        query
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    
    # Execute query
    result = await session.execute(query)
    return result.scalars().all()


async def delete_old_notifications(
    session: AsyncSession,
    days_old: int = 30
) -> int:
    """
    Delete notifications older than the specified number of days
    
    Args:
        session: Database session
        days_old: Age threshold in days
        
    Returns:
        int: Number of notifications deleted
    """
    threshold_date = datetime.utcnow() - timedelta(days=days_old)
    
    # Delete old notifications
    stmt = (
        delete(Notification)
        .where(Notification.created_at < threshold_date)
        .execution_options(synchronize_session="fetch")
    )
    
    result = await session.execute(stmt)
    await session.commit()
    
    deleted_count = result.rowcount
    logger.info(f"Deleted {deleted_count} notifications older than {days_old} days")
    
    return deleted_count
