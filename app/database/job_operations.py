# app/database/job_operations.py
"""
Database operations related to job listings for coBoarding platform
"""

import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_, func, text
from sqlalchemy.orm import joinedload
from loguru import logger

from .models import JobListing, Application


async def get_job_listing(session: AsyncSession, job_id: str) -> Optional[JobListing]:
    """
    Get a job listing by ID
    
    Args:
        session: Database session
        job_id: ID of the job listing to retrieve
        
    Returns:
        JobListing or None: The job listing if found, None otherwise
    """
    query = select(JobListing).where(JobListing.id == job_id)
    result = await session.execute(query)
    return result.scalars().first()


async def get_active_job_listings(
    session: AsyncSession, 
    limit: int = 100,
    offset: int = 0,
    sort_by: str = 'created_at',
    sort_order: str = 'desc'
) -> List[JobListing]:
    """
    Get active job listings
    
    Args:
        session: Database session
        limit: Maximum number of job listings to return
        offset: Number of job listings to skip
        sort_by: Field to sort by (default: 'created_at')
        sort_order: Sort order ('asc' or 'desc')
        
    Returns:
        list: List of active JobListing objects
    """
    # Current time for deadline comparison
    now = datetime.utcnow()
    
    # Build query for active listings
    query = (
        select(JobListing)
        .where(
            and_(
                JobListing.is_active == True,
                or_(
                    JobListing.deadline == None,
                    JobListing.deadline > now
                )
            )
        )
    )
    
    # Add sorting
    if hasattr(JobListing, sort_by):
        sort_column = getattr(JobListing, sort_by)
        if sort_order.lower() == 'desc':
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())
    
    # Add pagination
    query = query.limit(limit).offset(offset)
    
    # Execute query
    result = await session.execute(query)
    return result.scalars().all()


async def get_expired_job_listings(
    session: AsyncSession,
    limit: int = 100,
    offset: int = 0,
    include_closed: bool = False
) -> List[Dict[str, Any]]:
    """
    Get job listings that have passed their deadline
    
    Args:
        session: Database session
        limit: Maximum number of job listings to return
        offset: Number of job listings to skip
        include_closed: Whether to include already closed/expired listings
        
    Returns:
        list: List of expired JobListing objects
    """
    # Current time for deadline comparison
    now = datetime.utcnow()
    
    # Build query for expired listings
    query = select(JobListing)
    
    if include_closed:
        # Include all expired listings, regardless of is_active status
        query = query.where(
            and_(
                JobListing.deadline != None,
                JobListing.deadline < now
            )
        )
    else:
        # Only include listings that are still marked as active but have expired
        query = query.where(
            and_(
                JobListing.is_active == True,
                JobListing.deadline != None,
                JobListing.deadline < now
            )
        )
    
    # Add sorting and pagination
    query = (
        query
        .order_by(JobListing.deadline.asc())
        .limit(limit)
        .offset(offset)
    )
    
    # Execute query
    result = await session.execute(query)
    job_listings = result.scalars().all()
    
    # Get application counts for each job listing
    formatted_listings = []
    for job in job_listings:
        # Count applications for this job
        app_count_query = (
            select(func.count())
            .select_from(Application)
            .where(Application.job_listing_id == job.id)
        )
        app_count_result = await session.execute(app_count_query)
        application_count = app_count_result.scalar()
        
        # Calculate days expired
        days_expired = (now - job.deadline).days if job.deadline else 0
        
        formatted_listings.append({
            "id": job.id,
            "title": job.title,
            "company_name": job.company_name,
            "deadline": job.deadline.isoformat() if job.deadline else None,
            "days_expired": days_expired,
            "is_active": job.is_active,
            "application_count": application_count
        })
    
    return formatted_listings


async def create_job_listing(session: AsyncSession, job_data: dict) -> JobListing:
    """
    Create a new job listing
    
    Args:
        session: Database session
        job_data: Dictionary containing job listing data
        
    Returns:
        JobListing: The created job listing
    """
    job_listing = JobListing(
        id=str(uuid.uuid4()),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        **job_data
    )
    
    session.add(job_listing)
    await session.commit()
    await session.refresh(job_listing)
    
    logger.info(f"Created new job listing: {job_listing.id} - {job_listing.title}")
    return job_listing


async def update_job_listing(
    session: AsyncSession, 
    job_id: str, 
    update_data: dict
) -> bool:
    """
    Update a job listing
    
    Args:
        session: Database session
        job_id: ID of the job listing to update
        update_data: Dictionary of fields to update
        
    Returns:
        bool: True if update was successful, False if job listing not found
    """
    # Add updated_at timestamp
    update_data["updated_at"] = datetime.utcnow()
    
    # Update job listing
    stmt = (
        update(JobListing)
        .where(JobListing.id == job_id)
        .values(**update_data)
        .execution_options(synchronize_session="fetch")
    )
    
    result = await session.execute(stmt)
    await session.commit()
    
    if result.rowcount > 0:
        logger.info(f"Updated job listing {job_id}: {list(update_data.keys())}")
        return True
    else:
        logger.warning(f"Job listing not found for update: {job_id}")
        return False


async def deactivate_job_listing(session: AsyncSession, job_id: str) -> bool:
    """
    Deactivate a job listing
    
    Args:
        session: Database session
        job_id: ID of the job listing to deactivate
        
    Returns:
        bool: True if deactivation was successful, False if job listing not found
    """
    return await update_job_listing(
        session, 
        job_id, 
        {"is_active": False, "deactivated_at": datetime.utcnow()}
    )


async def search_job_listings(
    session: AsyncSession,
    search_term: str = None,
    location: str = None,
    category: str = None,
    active_only: bool = True,
    limit: int = 100,
    offset: int = 0
) -> List[JobListing]:
    """
    Search for job listings with various filters
    
    Args:
        session: Database session
        search_term: Optional search term to match against title and description
        location: Optional location filter
        category: Optional category filter
        active_only: If True, only return active job listings
        limit: Maximum number of job listings to return
        offset: Number of job listings to skip
        
    Returns:
        list: List of matching JobListing objects
    """
    # Start building the query
    query = select(JobListing)
    
    # Apply filters
    filters = []
    
    if active_only:
        now = datetime.utcnow()
        filters.append(JobListing.is_active == True)
        filters.append(
            or_(
                JobListing.deadline == None,
                JobListing.deadline > now
            )
        )
    
    if search_term:
        search_filter = or_(
            JobListing.title.ilike(f"%{search_term}%"),
            JobListing.description.ilike(f"%{search_term}%"),
            JobListing.company_name.ilike(f"%{search_term}%")
        )
        filters.append(search_filter)
    
    if location:
        filters.append(JobListing.location.ilike(f"%{location}%"))
    
    if category:
        filters.append(JobListing.category == category)
    
    # Apply all filters
    if filters:
        query = query.where(and_(*filters))
    
    # Add sorting and pagination
    query = (
        query
        .order_by(JobListing.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    
    # Execute query
    result = await session.execute(query)
    return result.scalars().all()
