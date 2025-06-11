"""
Data models for the coBoarding application.
"""
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, validator
from datetime import datetime

class CVData(BaseModel):
    """Model for CV data extracted from uploaded documents."""
    name: str
    email: str
    phone: Optional[str] = None
    title: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    experience: List[Dict[str, Any]] = Field(default_factory=list)
    education: List[Dict[str, Any]] = Field(default_factory=list)
    location: Optional[str] = None
    summary: Optional[str] = None
    raw_text: Optional[str] = None
    source_file: Optional[str] = None
    extracted_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class CompanyProfile(BaseModel):
    """Model for company profile data."""
    id: str
    company: str
    position: str
    required_skills: List[str] = Field(default_factory=list)
    preferred_skills: List[str] = Field(default_factory=list)
    location: Optional[str] = None
    remote: bool = False
    description: Optional[str] = None
    notification_email: Optional[str] = None
    slack_webhook_url: Optional[str] = None
    teams_webhook_url: Optional[str] = None
    whatsapp_number: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @validator('updated_at', pre=True, always=True)
    def update_timestamp(cls, v, values):
        return datetime.utcnow()


class ChatMessage(BaseModel):
    """Model for chat messages between candidates and employers."""
    id: str
    session_id: str
    sender: str  # 'candidate' or 'employer'
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Notification(BaseModel):
    """Model for notifications sent through the platform."""
    id: str
    type: str  # 'new_candidate', 'employer_response', etc.
    recipient: str  # email, phone, or channel ID
    recipient_type: str  # 'email', 'slack', 'teams', 'whatsapp'
    subject: str
    message: str
    status: str = 'pending'  # 'pending', 'sent', 'failed', 'delivered', 'read'
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    error: Optional[str] = None

    @validator('updated_at', pre=True, always=True)
    def update_timestamp(cls, v, values):
        return datetime.utcnow()


class MatchResult(BaseModel):
    """Model for match results between candidates and positions."""
    candidate_id: str
    company_id: str
    position_id: str
    score: float  # 0.0 to 1.0
    matched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    calculated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class JobApplication(BaseModel):
    """Model for tracking job applications."""
    id: str
    candidate_id: str
    company_id: str
    position_id: str
    status: str = 'applied'  # 'applied', 'reviewed', 'interviewing', 'offered', 'hired', 'rejected'
    application_data: Dict[str, Any] = Field(default_factory=dict)
    applied_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    status_changed_at: Dict[str, datetime] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('updated_at', pre=True, always=True)
    def update_timestamp(cls, v, values):
        return datetime.utcnow()

    def update_status(self, new_status: str):
        """Update the application status and track the change."""
        self.status_changed_at[self.status] = self.updated_at
        self.status = new_status
        self.updated_at = datetime.utcnow()
        self.status_changed_at[new_status] = self.updated_at


# Union type for all models
ModelType = Union[CVData, CompanyProfile, ChatMessage, Notification, MatchResult, JobApplication]
