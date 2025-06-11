"""
CV processing endpoints for the coBoarding API.
"""
import asyncio
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, UploadFile, File, BackgroundTasks, Depends, HTTPException
from fastapi.responses import JSONResponse
import aioredis

from app.core.cv_processor import CVProcessor
from ..models import CVUploadResponse
from ..dependencies import get_redis, get_session_id

router = APIRouter()


@router.post("/upload", response_model=CVUploadResponse)
async def upload_cv(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    redis: aioredis.Redis = Depends(get_redis)
):
    """
    Upload and process CV file.
    
    Args:
        file: Uploaded CV file
        background_tasks: Background tasks runner
        redis: Redis client dependency
        
    Returns:
        CVUploadResponse: CV processing results
    """
    try:
        # Generate session ID
        session_id = get_session_id()
        
        # Record start time for metrics
        start_time = datetime.utcnow()
        
        # Initialize CV processor
        cv_processor = CVProcessor()
        
        # Process the CV
        cv_data = await cv_processor.process_cv(file)
        
        # Calculate processing time
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        
        # Store CV data in Redis with 24-hour expiry
        await redis.setex(
            f"cv:{session_id}", 
            86400,  # 24 hours in seconds
            str(cv_data)
        )
        
        # Log processing metrics in background
        background_tasks.add_task(
            log_processing_metrics,
            session_id=session_id,
            cv_data=cv_data,
            start_time=start_time
        )
        
        return CVUploadResponse(
            session_id=session_id,
            cv_data=cv_data,
            processing_time=processing_time,
            success=True,
            message="CV processed successfully"
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Error processing CV: {str(e)}",
                "session_id": None,
                "cv_data": {},
                "processing_time": 0
            }
        )


@router.get("/{session_id}", response_model=Dict[str, Any])
async def get_cv_data(session_id: str, redis: aioredis.Redis = Depends(get_redis)):
    """
    Retrieve CV data by session ID.
    
    Args:
        session_id: Session ID from CV upload
        redis: Redis client dependency
        
    Returns:
        Dict: CV data
    """
    cv_data_str = await redis.get(f"cv:{session_id}")
    if not cv_data_str:
        raise HTTPException(status_code=404, detail="CV data not found")
    
    import ast
    return ast.literal_eval(cv_data_str)


@router.put("/{session_id}", response_model=Dict[str, Any])
async def update_cv_data(
    session_id: str, 
    cv_data: Dict[str, Any],
    redis: aioredis.Redis = Depends(get_redis)
):
    """
    Update CV data.
    
    Args:
        session_id: Session ID from CV upload
        cv_data: Updated CV data
        redis: Redis client dependency
        
    Returns:
        Dict: Updated CV data
    """
    await redis.setex(f"cv:{session_id}", 86400, str(cv_data))
    return cv_data


async def log_processing_metrics(session_id: str, cv_data: Dict, start_time: datetime):
    """
    Background task to log processing metrics.
    
    Args:
        session_id: Session ID
        cv_data: Processed CV data
        start_time: Processing start time
    """
    processing_time = (datetime.utcnow() - start_time).total_seconds()
    
    # In a production environment, this would log to a monitoring system
    print(f"CV Processing Metrics - Session: {session_id}, Time: {processing_time}s, "
          f"Fields extracted: {len(cv_data.keys())}")
