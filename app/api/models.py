"""
API data models for the coBoarding platform.
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr


class CVUploadResponse(BaseModel):
    """Response model for CV upload endpoint."""
    session_id: str
    cv_data: Dict[str, Any]
    processing_time: float
    success: bool
    message: str


class JobMatchResponse(BaseModel):
    """Response model for job matching endpoint."""
    matches: List[Dict[str, Any]]
    total_matches: int
    processing_time: float
    match_criteria: Dict[str, Any]


class ChatMessage(BaseModel):
    """Request model for chat message endpoint."""
    message: str
    company_id: str
    session_id: str


class ChatResponse(BaseModel):
    """Response model for chat message endpoint."""
    response: str
    timestamp: str
    session_id: str
    company_id: str


class TechnicalQuestion(BaseModel):
    """Model for technical validation questions."""
    question: str
    topic: str
    difficulty: str
    expected_answer_length: str


class TechnicalQuestionResponse(BaseModel):
    """Response model for technical questions endpoint."""
    questions: List[TechnicalQuestion]
    session_id: str
    company_id: str


class NotificationRequest(BaseModel):
    """Request model for notification endpoint."""
    session_id: str
    company_id: str
    message: str
    notification_type: str = "candidate_application"


class HealthResponse(BaseModel):
    """Response model for health check endpoint."""
    status: str
    timestamp: str
    services: Dict[str, str]
