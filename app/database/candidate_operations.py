# app/database/candidate_operations.py
"""
Database operations related to candidates for coBoarding platform
"""

import uuid
from typing import Tuple, Optional, Dict, Any, List
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_, func, text
from sqlalchemy.orm import joinedload
from loguru import logger

from .models import Candidate, Application, Notification, AuditLog


async def get_or_create_candidate_by_email(
    session: AsyncSession, 
    email: str, 
    **candidate_data
) -> Tuple[Candidate, bool]:
    """
    Get an existing candidate by email or create a new one if not found.
    
    Args:
        session: Database session
        email: Candidate's email address
        **candidate_data: Additional candidate data for creation
        
    Returns:
        tuple: (candidate, created) where created is a boolean indicating if the candidate was created
    """
    # Check if candidate exists
    query = select(Candidate).where(Candidate.email == email)
    result = await session.execute(query)
    candidate = result.scalars().first()
    
    if candidate:
        return candidate, False
    
    # Create new candidate
    new_candidate = Candidate(
        id=str(uuid.uuid4()),
        email=email,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        **candidate_data
    )
    
    session.add(new_candidate)
    await session.commit()
    await session.refresh(new_candidate)
    
    logger.info(f"Created new candidate: {new_candidate.id} ({email})")
    return new_candidate, True


async def update_candidate_data(
    session: AsyncSession, 
    candidate_id: str, 
    update_data: dict
) -> bool:
    """
    Update candidate data by ID
    
    Args:
        session: Database session
        candidate_id: ID of the candidate to update
        update_data: Dictionary of fields to update
        
    Returns:
        bool: True if update was successful, False if candidate not found
    """
    # Add updated_at timestamp
    update_data["updated_at"] = datetime.utcnow()
    
    # Update candidate
    stmt = (
        update(Candidate)
        .where(Candidate.id == candidate_id)
        .values(**update_data)
        .execution_options(synchronize_session="fetch")
    )
    
    result = await session.execute(stmt)
    await session.commit()
    
    if result.rowcount > 0:
        logger.info(f"Updated candidate {candidate_id}: {list(update_data.keys())}")
        return True
    else:
        logger.warning(f"Candidate not found for update: {candidate_id}")
        return False


async def create_candidate(session: AsyncSession, candidate_data: dict) -> Candidate:
    """Create a new candidate record"""
    candidate = Candidate(
        id=str(uuid.uuid4()),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        **candidate_data
    )
    session.add(candidate)
    await session.commit()
    await session.refresh(candidate)
    return candidate


async def get_candidate_by_session(session: AsyncSession, session_id: str) -> Optional[Candidate]:
    """Get candidate by session ID"""
    query = select(Candidate).where(Candidate.session_id == session_id)
    result = await session.execute(query)
    return result.scalars().first()


async def get_candidate_by_email(session: AsyncSession, email: str) -> Optional[Candidate]:
    """
    Get a candidate by their email address
    
    Args:
        session: Database session
        email: Email address of the candidate
        
    Returns:
        Candidate or None: The candidate if found, None otherwise
    """
    query = select(Candidate).where(Candidate.email == email)
    result = await session.execute(query)
    return result.scalars().first()


async def delete_candidate_data(
    session: AsyncSession, 
    candidate_id: str, 
    anonymize: bool = True
) -> bool:
    """
    Delete or anonymize a candidate's personal data for GDPR compliance
    
    Args:
        session: Database session
        candidate_id: ID of the candidate
        anonymize: If True, anonymize the data instead of deleting it
        
    Returns:
        bool: True if successful, False otherwise
    """
    # Check if candidate exists
    query = select(Candidate).where(Candidate.id == candidate_id)
    result = await session.execute(query)
    candidate = result.scalars().first()
    
    if not candidate:
        logger.warning(f"Candidate not found for deletion/anonymization: {candidate_id}")
        return False
    
    if anonymize:
        # Anonymize candidate data
        return await anonymize_candidate_data(session, candidate_id)
    else:
        # Delete candidate and related data
        try:
            # Delete related applications
            app_stmt = delete(Application).where(Application.candidate_id == candidate_id)
            await session.execute(app_stmt)
            
            # Delete related notifications
            notif_stmt = delete(Notification).where(Notification.recipient_id == candidate_id)
            await session.execute(notif_stmt)
            
            # Delete candidate
            cand_stmt = delete(Candidate).where(Candidate.id == candidate_id)
            await session.execute(cand_stmt)
            
            await session.commit()
            logger.info(f"Deleted candidate and related data: {candidate_id}")
            return True
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to delete candidate {candidate_id}: {e}")
            return False


async def anonymize_candidate_data(session: AsyncSession, candidate_id: str) -> bool:
    """
    Anonymize a candidate's personal data for GDPR compliance
    
    Args:
        session: Database session
        candidate_id: ID of the candidate to anonymize
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Generate anonymized values
        anon_email = f"anonymized_{candidate_id[:8]}@example.com"
        anon_name = f"Anonymized User {candidate_id[:6]}"
        
        # Update candidate with anonymized data
        update_data = {
            "email": anon_email,
            "first_name": anon_name,
            "last_name": "",
            "phone": "0000000000",
            "address": "",
            "resume_text": "This content has been anonymized for privacy compliance.",
            "resume_file_path": None,
            "profile_image_path": None,
            "is_anonymized": True,
            "updated_at": datetime.utcnow()
        }
        
        stmt = (
            update(Candidate)
            .where(Candidate.id == candidate_id)
            .values(**update_data)
        )
        
        result = await session.execute(stmt)
        
        if result.rowcount == 0:
            logger.warning(f"Candidate not found for anonymization: {candidate_id}")
            return False
        
        await session.commit()
        logger.info(f"Anonymized candidate data: {candidate_id}")
        return True
        
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to anonymize candidate {candidate_id}: {e}")
        return False


async def export_candidate_data(session: AsyncSession, candidate_id: str) -> Dict[str, Any]:
    """
    Export all data related to a candidate in a structured format for GDPR compliance.
    
    Args:
        session: Database session
        candidate_id: ID of the candidate whose data to export
        
    Returns:
        dict: A dictionary containing all the candidate's data in a structured format
    """
    # Get candidate data
    candidate_query = select(Candidate).where(Candidate.id == candidate_id)
    candidate_result = await session.execute(candidate_query)
    candidate = candidate_result.scalars().first()
    
    if not candidate:
        logger.warning(f"Candidate not found for data export: {candidate_id}")
        return {"error": "Candidate not found"}
    
    # Get applications
    app_query = (
        select(Application)
        .options(joinedload(Application.job_listing))
        .where(Application.candidate_id == candidate_id)
    )
    app_result = await session.execute(app_query)
    applications = app_result.scalars().all()
    
    # Get notifications
    notif_query = (
        select(Notification)
        .where(Notification.recipient_id == candidate_id)
    )
    notif_result = await session.execute(notif_query)
    notifications = notif_result.scalars().all()
    
    # Get audit logs
    audit_query = (
        select(AuditLog)
        .where(
            or_(
                AuditLog.user_id == candidate_id,
                and_(AuditLog.target_id == candidate_id, AuditLog.target_type == "candidate")
            )
        )
    )
    audit_result = await session.execute(audit_query)
    audit_logs = audit_result.scalars().all()
    
    # Compile export data
    export_data = {
        "candidate": {
            "id": candidate.id,
            "email": candidate.email,
            "first_name": candidate.first_name,
            "last_name": candidate.last_name,
            "phone": candidate.phone,
            "address": candidate.address,
            "created_at": candidate.created_at.isoformat() if candidate.created_at else None,
            "updated_at": candidate.updated_at.isoformat() if candidate.updated_at else None,
            "session_id": candidate.session_id,
            "expires_at": candidate.expires_at.isoformat() if candidate.expires_at else None,
            "is_anonymized": candidate.is_anonymized
        },
        "applications": [
            {
                "id": app.id,
                "job_title": app.job_listing.title if app.job_listing else "Unknown",
                "company": app.job_listing.company_name if app.job_listing else "Unknown",
                "status": app.status,
                "match_score": app.match_score,
                "applied_at": app.created_at.isoformat() if app.created_at else None,
                "updated_at": app.updated_at.isoformat() if app.updated_at else None
            }
            for app in applications
        ],
        "notifications": [
            {
                "id": notif.id,
                "type": notif.notification_type,
                "title": notif.title,
                "message": notif.message,
                "status": notif.delivery_status,
                "sent_at": notif.sent_at.isoformat() if notif.sent_at else None,
                "created_at": notif.created_at.isoformat() if notif.created_at else None
            }
            for notif in notifications
        ],
        "audit_logs": [
            {
                "event_type": log.event_type,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                "details": log.details
            }
            for log in audit_logs
        ]
    }
    
    logger.info(f"Exported data for candidate: {candidate_id}")
    return export_data


async def get_candidate_applications(
    session: AsyncSession, 
    candidate_id: str, 
    limit: int = 100, 
    offset: int = 0
) -> List[Dict[str, Any]]:
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
    query = (
        select(Application)
        .options(joinedload(Application.job_listing))
        .where(Application.candidate_id == candidate_id)
        .order_by(Application.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    
    result = await session.execute(query)
    applications = result.scalars().all()
    
    # Format results
    formatted_applications = []
    for app in applications:
        job_listing = app.job_listing
        formatted_applications.append({
            "id": app.id,
            "status": app.status,
            "match_score": app.match_score,
            "created_at": app.created_at.isoformat() if app.created_at else None,
            "updated_at": app.updated_at.isoformat() if app.updated_at else None,
            "job_listing": {
                "id": job_listing.id if job_listing else None,
                "title": job_listing.title if job_listing else "Unknown",
                "company_name": job_listing.company_name if job_listing else "Unknown",
                "location": job_listing.location if job_listing else None,
                "deadline": job_listing.deadline.isoformat() if job_listing and job_listing.deadline else None
            }
        })
    
    return formatted_applications
