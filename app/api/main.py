"""
Main FastAPI application for coBoarding platform.
"""
import asyncio
import os

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import create_app

# Create FastAPI application
app = create_app()

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"detail": "Resource not found", "path": request.url.path}
    )

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "message": str(exc)}
    )

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize connections and services on startup."""
    # Initialize Redis connection pool
    from .dependencies import get_redis
    redis = await get_redis()
    await redis.ping()
    print("Connected to Redis")
    
    # Initialize other services as needed
    print("API server started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up connections on shutdown."""
    # Close Redis connection pool
    from .dependencies import redis_pool
    if redis_pool:
        await redis_pool.close()
    
    print("API server shut down successfully")

if __name__ == "__main__":
    uvicorn.run(
        "app.api.main:app", 
        host="0.0.0.0", 
        port=int(os.getenv("PORT", 8000)),
        reload=True
    )
