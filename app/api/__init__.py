"""
FastAPI backend server for coBoarding platform
Provides REST API endpoints for CV processing, job matching, and communication
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import (
    cv_router,
    job_router,
    chat_router,
    form_router,
    gdpr_router,
    health_router
)
from .dependencies import get_redis, get_session_id, get_current_user
from .models import (
    CVUploadResponse,
    JobMatchResponse,
    ChatMessage,
    ChatResponse,
    TechnicalQuestion,
    TechnicalQuestionResponse,
    NotificationRequest,
    HealthResponse
)

__all__ = [
    'create_app',
    'get_redis',
    'get_session_id',
    'get_current_user',
    'CVUploadResponse',
    'JobMatchResponse',
    'ChatMessage',
    'ChatResponse',
    'TechnicalQuestion',
    'TechnicalQuestionResponse',
    'NotificationRequest',
    'HealthResponse'
]


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="coBoarding API",
        description="Speed Hiring Platform for SME Tech Companies",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(health_router.router, tags=["Health"])
    app.include_router(cv_router.router, prefix="/cv", tags=["CV Processing"])
    app.include_router(job_router.router, prefix="/jobs", tags=["Job Matching"])
    app.include_router(chat_router.router, prefix="/chat", tags=["Chat"])
    app.include_router(form_router.router, prefix="/forms", tags=["Form Automation"])
    app.include_router(gdpr_router.router, prefix="/gdpr", tags=["GDPR Compliance"])

    return app
