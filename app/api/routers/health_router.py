"""
Health check endpoints for the coBoarding API.
"""
import asyncio
from datetime import datetime
import platform
import sys
import os

from fastapi import APIRouter, Depends
import aioredis

from ..models import HealthResponse
from ..dependencies import get_redis

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(redis: aioredis.Redis = Depends(get_redis)):
    """
    Health check endpoint for monitoring.
    
    Args:
        redis: Redis client dependency
        
    Returns:
        HealthResponse: Health status of the API and its dependencies
    """
    services = {
        "api": "ok",
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "platform": platform.platform(),
    }
    
    # Check Redis connection
    try:
        await redis.ping()
        services["redis"] = "ok"
    except Exception as e:
        services["redis"] = f"error: {str(e)}"
    
    # Check database connection
    try:
        from app.database.connection import get_db_session
        async with get_db_session() as session:
            services["database"] = "ok"
    except Exception as e:
        services["database"] = f"error: {str(e)}"
    
    # Check file storage
    temp_dir = os.path.join(os.getcwd(), "temp_uploads")
    if os.path.exists(temp_dir) and os.access(temp_dir, os.W_OK):
        services["file_storage"] = "ok"
    else:
        services["file_storage"] = "error: temp directory not accessible"
    
    return HealthResponse(
        status="ok" if all(v == "ok" for k, v in services.items() if k != "python" and k != "platform") else "error",
        timestamp=datetime.utcnow().isoformat(),
        services=services
    )
