# app/database/application_operations.py
"""
Database operations related to job applications for coBoarding platform
"""

import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_, func, text
from sqlalchemy.orm import joinedload
from loguru import logger

from .models import Application, JobListing, Candidate


async def create_application(session: AsyncSession, application_data: dict) -> Application:
    """Create a new application record"""
    application = Application(
        id=str(uuid.uuid4()),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        **application_data
    )
    session.add(application)
    await session.commit()
    await session.refresh(application)
    return application


async def get_application(session: AsyncSession, application_id: str) -> Optional[Application]:
    """
    Get an application by ID
    
    Args:
        session: Database session
        application_id: ID of the application to retrieve
        
    Returns:
        Application or None: The application if found, None otherwise
    """
    query = (
        select(Application)
        .options(joinedload(Application.candidate), joinedload(Application.job_listing))
        .where(Application.id == application_id)
    )
    result = await session.execute(query)
    return result.scalars().first()


async def update_application_status(
    session: AsyncSession, 
    application_id: str, 
    new_status: str, 
    status_message: str = None
) -> bool:
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
    # Update application
    update_data = {
        "status": new_status,
        "status_message": status_message,
        "updated_at": datetime.utcnow()
    }
    
    stmt = (
        update(Application)
        .where(Application.id == application_id)
        .values(**update_data)
        .execution_options(synchronize_session="fetch")
    )
    
    result = await session.execute(stmt)
    await session.commit()
    
    if result.rowcount > 0:
        logger.info(f"Updated application {application_id} status to {new_status}")
        return True
    else:
        logger.warning(f"Application not found for status update: {application_id}")
        return False


async def get_applications_for_job_listing(
    session: AsyncSession,
    job_listing_id: str,
    limit: int = 100,
    offset: int = 0,
    status: str = None,
    sort_by: str = 'created_at',
    sort_order: str = 'desc'
) -> List[Dict[str, Any]]:
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
    # Build query
    query = (
        select(Application)
        .options(joinedload(Application.candidate))
        .where(Application.job_listing_id == job_listing_id)
    )
    
    # Add status filter if provided
    if status:
        query = query.where(Application.status == status)
    
    # Add sorting
    if hasattr(Application, sort_by):
        sort_column = getattr(Application, sort_by)
        if sort_order.lower() == 'desc':
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())
    
    # Add pagination
    query = query.limit(limit).offset(offset)
    
    # Execute query
    result = await session.execute(query)
    applications = result.scalars().all()
    
    # Format results
    formatted_applications = []
    for app in applications:
        candidate = app.candidate
        formatted_applications.append({
            "id": app.id,
            "status": app.status,
            "match_score": app.match_score,
            "created_at": app.created_at.isoformat() if app.created_at else None,
            "updated_at": app.updated_at.isoformat() if app.updated_at else None,
            "candidate": {
                "id": candidate.id if candidate else None,
                "email": candidate.email if candidate else None,
                "first_name": candidate.first_name if candidate else None,
                "last_name": candidate.last_name if candidate else None
            }
        })
    
    return formatted_applications


async def get_applications_for_candidate(
    session: AsyncSession, 
    candidate_id: str,
    limit: int = 100,
    offset: int = 0,
    status: str = None
) -> List[Application]:
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
    # Build query
    query = (
        select(Application)
        .options(joinedload(Application.job_listing))
        .where(Application.candidate_id == candidate_id)
    )
    
    # Add status filter if provided
    if status:
        query = query.where(Application.status == status)
    
    # Add sorting and pagination
    query = query.order_by(Application.created_at.desc()).limit(limit).offset(offset)
    
    # Execute query
    result = await session.execute(query)
    return result.scalars().all()


async def get_application_by_session_and_job(
    session: AsyncSession, 
    session_id: str, 
    job_listing_id: str
) -> Optional[Application]:
    """
    Get an application by session ID and job listing ID
    
    Args:
        session: Database session
        session_id: Session ID of the candidate
        job_listing_id: ID of the job listing
        
    Returns:
        Application or None: The application if found, None otherwise
    """
    # First get the candidate by session ID
    candidate_query = select(Candidate).where(Candidate.session_id == session_id)
    candidate_result = await session.execute(candidate_query)
    candidate = candidate_result.scalars().first()
    
    if not candidate:
        logger.warning(f"No candidate found with session ID: {session_id}")
        return None
    
    # Now get the application
    app_query = (
        select(Application)
        .options(joinedload(Application.job_listing))
        .where(
            and_(
                Application.candidate_id == candidate.id,
                Application.job_listing_id == job_listing_id
            )
        )
    )
    
    app_result = await session.execute(app_query)
    application = app_result.scalars().first()
    
    return application


async def get_overdue_applications(
    session: AsyncSession,
    days_overdue: int = 7,
    limit: int = 100,
    offset: int = 0
) -> List[Dict[str, Any]]:
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
    # Calculate overdue date threshold
    overdue_date = datetime.utcnow() - timedelta(days=days_overdue)
    
    # Build query for applications that are still in "pending" status
    # and were created before the overdue threshold
    query = (
        select(Application)
        .options(
            joinedload(Application.candidate),
            joinedload(Application.job_listing)
        )
        .where(
            and_(
                Application.status == "pending",
                Application.created_at < overdue_date
            )
        )
        .order_by(Application.created_at.asc())
        .limit(limit)
        .offset(offset)
    )
    
    # Execute query
    result = await session.execute(query)
    applications = result.scalars().all()
    
    # Format results
    formatted_applications = []
    for app in applications:
        candidate = app.candidate
        job_listing = app.job_listing
        
        formatted_applications.append({
            "id": app.id,
            "created_at": app.created_at.isoformat() if app.created_at else None,
            "days_pending": (datetime.utcnow() - app.created_at).days if app.created_at else None,
            "candidate": {
                "id": candidate.id if candidate else None,
                "email": candidate.email if candidate else None,
                "name": f"{candidate.first_name} {candidate.last_name}" if candidate else "Unknown"
            },
            "job": {
                "id": job_listing.id if job_listing else None,
                "title": job_listing.title if job_listing else "Unknown",
                "company": job_listing.company_name if job_listing else "Unknown"
            }
        })
    
    return formatted_applications
