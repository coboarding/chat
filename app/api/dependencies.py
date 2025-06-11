"""
Dependency injection functions for the coBoarding API.
"""
import os
import uuid
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import aioredis

# Initialize security
security = HTTPBearer()

# Redis connection pool
redis_pool = None


async def get_redis() -> aioredis.Redis:
    """
    Get Redis client dependency.
    
    Returns:
        aioredis.Redis: Redis client
    """
    global redis_pool
    if redis_pool is None:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        redis_pool = aioredis.ConnectionPool.from_url(redis_url, decode_responses=True)
    
    return aioredis.Redis(connection_pool=redis_pool)


def get_session_id() -> str:
    """
    Generate new session ID.
    
    Returns:
        str: Unique session ID
    """
    return str(uuid.uuid4())


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Simple authentication for API access.
    
    Args:
        credentials: Bearer token credentials
        
    Returns:
        dict: User information
        
    Raises:
        HTTPException: If authentication fails
    """
    api_key = os.getenv("API_KEY", "development_key")
    if credentials.credentials != api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"authenticated": True}
