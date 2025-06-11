# app/database/models.py
"""
SQLAlchemy database models for coBoarding platform
Defines all database tables with relationships and constraints
"""

from datetime import datetime, timedelta
import uuid
from typing import Dict, List, Optional

from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    DateTime,
    Text,
    DECIMAL,
    ForeignKey,
    Index,
    CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func

Base = declarative_base()


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps"""
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


class UUIDMixin:
    """Mixin for UUID primary key"""
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class Candidate(Base, UUIDMixin, TimestampMixin):
    """Candidate information extracted from CV"""
    __tablename__ = 'candidates'

    # Unique session identifier for GDPR compliance
    session_id = Column(String(255), unique=True, nullable=False, index=True)

    # Personal information
    name = Column(String(255))
    email = Column(String(255), index=True)
    phone = Column(String(50))
    location = Column(String(255))

    # Professional information
    title = Column(String(255))
    summary = Column(Text)
    experience_years = Column(Integer, default=0)

    # Skills and qualifications (stored as JSON array)
    skills = Column(JSONB, default=list)
    programming_languages = Column(JSONB, default=list)
    frameworks = Column(JSONB, default=list)
    certifications = Column(JSONB, default=list)
    languages = Column(JSONB, default=list)

    # Education and experience (stored as JSON objects)
    education = Column(JSONB, default=list)
    experience = Column(JSONB, default=list)

    # Social profiles
    linkedin = Column(String(500))
    github = Column(String(500))
    website = Column(String(500))

    # Complete CV data for backup/audit
    cv_data = Column(JSONB)

    # File information
    file_path = Column(String(500))
    file_name = Column(String(255))
    file_type = Column(String(100))

    # GDPR compliance - automatic expiration
    expires_at = Column(
        DateTime,
        default=lambda: datetime.utcnow() + timedelta(hours=24),
        nullable=False,
        index=True
    )

    # Status tracking
    status = Column(String(50), default='active')  # active, expired, deleted

    # Relationships
    applications = relationship("Application", back_populates="candidate", cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        CheckConstraint('experience_years >= 0', name='check_experience_years_positive'),
        CheckConstraint("status IN ('active', 'expired', 'deleted')", name='check_status_valid'),
        Index('idx_candidates_expires_at', 'expires_at'),
        Index('idx_candidates_email_active', 'email', 'status'),
    )

    @validates('email')
    def validate_email(self, key, email):
        """Basic email validation"""
        if email and '@' not in email:
            raise ValueError('Invalid email format')
        return email

    @property
    def is_expired(self) -> bool:
        """Check if candidate data has expired"""
        return datetime.utcnow() > self.expires_at

    def to_dict(self) -> Dict:
        """Convert to dictionary for API responses"""
        return {
            'id': str(self.id),
            'session_id': self.session_id,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'location': self.location,
            'title': self.title,
            'summary': self.summary,
            'experience_years': self.experience_years,
            'skills': self.skills,
            'programming_languages': self.programming_languages,
            'frameworks': self.frameworks,
            'certifications': self.certifications,
            'languages': self.languages,
            'education': self.education,
            'experience': self.experience,
            'linkedin': self.linkedin,
            'github': self.github,
            'website': self.website,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat(),
            'status': self.status
        }


class JobListing(Base, UUIDMixin, TimestampMixin):
    """Job listings from companies"""
    __tablename__ = 'job_listings'

    # Company information
    company_name = Column(String(255), nullable=False)
    company_size = Column(String(50))  # startup, small, medium, large
    company_industry = Column(String(100))

    # Position details
    position = Column(String(255), nullable=False)
    department = Column(String(100))
    seniority_level = Column(String(50))  # junior, mid, senior, lead, principal

    # Location and remote work
    location = Column(String(255))
    remote = Column(Boolean, default=False)
    hybrid = Column(Boolean, default=False)
    relocation_assistance = Column(Boolean, default=False)

    # Requirements and qualifications
    requirements = Column(JSONB, default=list)  # Technical requirements
    nice_to_have = Column(JSONB, default=list)  # Preferred qualifications
    languages_required = Column(JSONB, default=list)  # Language requirements

    # Job details
    job_description = Column(Text)
    responsibilities = Column(JSONB, default=list)
    benefits = Column(JSONB, default=list)

    # Compensation
    salary_min = Column(Integer)
    salary_max = Column(Integer)
    salary_currency = Column(String(10), default='EUR')
    salary_range = Column(String(100))  # Human readable format
    equity = Column(Boolean, default=False)

    # Urgency and priority
    urgent = Column(Boolean, default=False)
    priority = Column(String(20), default='normal')  # low, normal, high, urgent
    response_time_hours = Column(Integer, default=24)

    # Application process
    application_process = Column(JSONB, default=dict)
    technical_interview = Column(Boolean, default=True)
    take_home_assignment = Column(Boolean, default=False)

    # Notification configuration
    notification_config = Column(JSONB, default=dict)

    # Status and visibility
    active = Column(Boolean, default=True, index=True)
    featured = Column(Boolean, default=False)
    posted_date = Column(DateTime, default=func.now())
    expires_date = Column(DateTime)

    # Metrics
    views_count = Column(Integer, default=0)
    applications_count = Column(Integer, default=0)

    # Relationships
    applications = relationship("Application", back_populates="job_listing", cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        CheckConstraint('salary_min >= 0', name='check_salary_min_positive'),
        CheckConstraint('salary_max >= salary_min', name='check_salary_max_greater_than_min'),
        CheckConstraint('response_time_hours > 0', name='check_response_time_positive'),
        CheckConstraint("priority IN ('low', 'normal', 'high', 'urgent')", name='check_priority_valid'),
        CheckConstraint("seniority_level IN ('junior', 'mid', 'senior', 'lead', 'principal')",
                        name='check_seniority_valid'),
        Index('idx_job_listings_active_urgent', 'active', 'urgent'),
        Index('idx_job_listings_location', 'location'),
        Index('idx_job_listings_remote', 'remote'),
    )

    @property
    def is_expired(self) -> bool:
        """Check if job listing has expired"""
        if self.expires_date:
            return datetime.utcnow() > self.expires_date
        return False

    def to_dict(self) -> Dict:
        """Convert to dictionary for API responses"""
        return {
            'id': str(self.id),
            'company_name': self.company_name,
            'company_size': self.company_size,
            'company_industry': self.company_industry,
            'position': self.position,
            'department': self.department,
            'seniority_level': self.seniority_level,
            'location': self.location,
            'remote': self.remote,
            'hybrid': self.hybrid,
            'relocation_assistance': self.relocation_assistance,
            'requirements': self.requirements,
            'nice_to_have': self.nice_to_have,
            'languages_required': self.languages_required,
            'job_description': self.job_description,
            'responsibilities': self.responsibilities,
            'benefits': self.benefits,
            'salary_min': self.salary_min,
            'salary_max': self.salary_max,
            'salary_currency': self.salary_currency,
            'salary_range': self.salary_range,
            'equity': self.equity,
            'urgent': self.urgent,
            'priority': self.priority,
            'response_time_hours': self.response_time_hours,
            'application_process': self.application_process,
            'technical_interview': self.technical_interview,
            'take_home_assignment': self.take_home_assignment,
            'notification_config': self.notification_config,
            'active': self.active,
            'featured': self.featured,
            'posted_date': self.posted_date.isoformat(),
            'expires_date': self.expires_date.isoformat() if self.expires_date else None,
            'views_count': self.views_count,
            'applications_count': self.applications_count,
            'created_at': self.created_at.isoformat()
        }


class Application(Base, UUIDMixin, TimestampMixin):
    """Job applications linking candidates to job listings"""
    __tablename__ = 'applications'

    # Foreign keys
    candidate_id = Column(UUID(as_uuid=True), ForeignKey('candidates.id', ondelete='CASCADE'), nullable=False)
    job_listing_id = Column(UUID(as_uuid=True), ForeignKey('job_listings.id', ondelete='CASCADE'), nullable=False)

    # Application scoring and matching
    match_score = Column(DECIMAL(5, 2), default=0.00)  # 0.00 to 100.00
    skills_match_count = Column(Integer, default=0)
    skills_total_count = Column(Integer, default=0)
    matching_skills = Column(JSONB, default=list)
    missing_skills = Column(JSONB, default=list)

    # Application status workflow
    status = Column(String(50), default='pending', nullable=False, index=True)
    # Status flow: pending -> screening -> technical_questions -> interview -> offer -> hired/rejected

    # Communication and conversation data
    conversation_data = Column(JSONB, default=dict)
    last_message_at = Column(DateTime)
    candidate_last_seen = Column(DateTime)
    employer_last_seen = Column(DateTime)

    # Technical validation (anti-spam)
    technical_questions = Column(JSONB, default=list)
    technical_answers = Column(JSONB, default=list)
    technical_score = Column(DECIMAL(5, 2))
    technical_validated = Column(Boolean, default=False)

    # Response tracking
    response_deadline = Column(
        DateTime,
        default=lambda: datetime.utcnow() + timedelta(hours=24),
        nullable=False,
        index=True
    )
    employer_responded_at = Column(DateTime)
    candidate_responded_at = Column(DateTime)

    # Application source and method
    application_source = Column(String(100))  # website, portal, direct, referral
    application_method = Column(String(50), default='automated')  # automated, manual

    # Additional data
    cover_letter = Column(Text)
    additional_notes = Column(Text)
    recruiter_notes = Column(Text)

    # Relationships
    candidate = relationship("Candidate", back_populates="applications")
    job_listing = relationship("JobListing", back_populates="applications")
    notifications = relationship("Notification", back_populates="application", cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        CheckConstraint('match_score >= 0 AND match_score <= 100', name='check_match_score_range'),
        CheckConstraint('technical_score >= 0 AND technical_score <= 100', name='check_technical_score_range'),
        CheckConstraint('skills_match_count >= 0', name='check_skills_match_count_positive'),
        CheckConstraint('skills_total_count >= 0', name='check_skills_total_count_positive'),
        CheckConstraint(
            "status IN ('pending', 'screening', 'technical_questions', 'interview', 'offer', 'hired', 'rejected', 'withdrawn')",
            name='check_status_valid'
        ),
        CheckConstraint(
            "application_method IN ('automated', 'manual')",
            name='check_application_method_valid'
        ),
        Index('idx_applications_candidate_job', 'candidate_id', 'job_listing_id'),
        Index('idx_applications_status_deadline', 'status', 'response_deadline'),
        Index('idx_applications_match_score', 'match_score'),
    )

    @property
    def is_overdue(self) -> bool:
        """Check if response deadline has passed"""
        return datetime.utcnow() > self.response_deadline

    @property
    def match_percentage(self) -> float:
        """Get match score as percentage"""
        return float(self.match_score) if self.match_score else 0.0

    def to_dict(self) -> Dict:
        """Convert to dictionary for API responses"""
        return {
            'id': str(self.id),
            'candidate_id': str(self.candidate_id),
            'job_listing_id': str(self.job_listing_id),
            'match_score': float(self.match_score) if self.match_score else 0.0,
            'skills_match_count': self.skills_match_count,
            'skills_total_count': self.skills_total_count,
            'matching_skills': self.matching_skills,
            'missing_skills': self.missing_skills,
            'status': self.status,
            'conversation_data': self.conversation_data,
            'last_message_at': self.last_message_at.isoformat() if self.last_message_at else None,
            'technical_questions': self.technical_questions,
            'technical_answers': self.technical_answers,
            'technical_score': float(self.technical_score) if self.technical_score else None,
            'technical_validated': self.technical_validated,
            'response_deadline': self.response_deadline.isoformat(),
            'employer_responded_at': self.employer_responded_at.isoformat() if self.employer_responded_at else None,
            'candidate_responded_at': self.candidate_responded_at.isoformat() if self.candidate_responded_at else None,
            'application_source': self.application_source,
            'application_method': self.application_method,
            'cover_letter': self.cover_letter,
            'additional_notes': self.additional_notes,
            'recruiter_notes': self.recruiter_notes,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class Notification(Base, UUIDMixin, TimestampMixin):
    """Notification delivery tracking"""
    __tablename__ = 'notifications'

    # Foreign key
    application_id = Column(UUID(as_uuid=True), ForeignKey('applications.id', ondelete='CASCADE'), nullable=False)

    # Notification details
    notification_type = Column(String(50), nullable=False)  # candidate_application, employer_response, reminder, etc.
    channel = Column(String(50), nullable=False)  # email, slack, teams, whatsapp, sms
    recipient = Column(String(255), nullable=False)  # email address, phone number, webhook URL

    # Message content
    subject = Column(String(500))
    message_data = Column(JSONB)
    template_used = Column(String(100))

    # Delivery tracking
    sent_at = Column(DateTime, index=True)
    delivery_status = Column(String(50), default='pending', nullable=False)  # pending, sent, delivered, failed, bounced
    delivery_attempts = Column(Integer, default=0)
    error_message = Column(Text)
    external_id = Column(String(255))  # ID from external service (Slack, Teams, etc.)

    # Response tracking
    opened_at = Column(DateTime)
    clicked_at = Column(DateTime)
    responded_at = Column(DateTime)

    # Retry logic
    next_retry_at = Column(DateTime)
    max_retries = Column(Integer, default=3)

    # Relationships
    application = relationship("Application", back_populates="notifications")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "notification_type IN ('candidate_application', 'employer_response', 'reminder', 'deadline_warning', 'status_update')",
            name='check_notification_type_valid'
        ),
        CheckConstraint(
            "channel IN ('email', 'slack', 'teams', 'whatsapp', 'sms', 'webhook')",
            name='check_channel_valid'
        ),
        CheckConstraint(
            "delivery_status IN ('pending', 'sent', 'delivered', 'failed', 'bounced', 'spam')",
            name='check_delivery_status_valid'
        ),
        CheckConstraint('delivery_attempts >= 0', name='check_delivery_attempts_positive'),
        CheckConstraint('max_retries >= 0', name='check_max_retries_positive'),
        Index('idx_notifications_application_type', 'application_id', 'notification_type'),
        Index('idx_notifications_delivery_status', 'delivery_status'),
        Index('idx_notifications_sent_at', 'sent_at'),
    )

    def to_dict(self) -> Dict:
        """Convert to dictionary for API responses"""
        return {
            'id': str(self.id),
            'application_id': str(self.application_id),
            'notification_type': self.notification_type,
            'channel': self.channel,
            'recipient': self.recipient,
            'subject': self.subject,
            'message_data': self.message_data,
            'template_used': self.template_used,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'delivery_status': self.delivery_status,
            'delivery_attempts': self.delivery_attempts,
            'error_message': self.error_message,
            'external_id': self.external_id,
            'opened_at': self.opened_at.isoformat() if self.opened_at else None,
            'clicked_at': self.clicked_at.isoformat() if self.clicked_at else None,
            'responded_at': self.responded_at.isoformat() if self.responded_at else None,
            'next_retry_at': self.next_retry_at.isoformat() if self.next_retry_at else None,
            'max_retries': self.max_retries,
            'created_at': self.created_at.isoformat()
        }


class AuditLog(Base, UUIDMixin, TimestampMixin):
    """Audit trail for GDPR compliance and security"""
    __tablename__ = 'audit_logs'

    # Session and user tracking
    session_id = Column(String(255), index=True)
    user_id = Column(String(255))
    ip_address = Column(String(45))  # IPv6 compatible
    user_agent = Column(Text)

    # Action details
    action = Column(String(100), nullable=False)  # create, read, update, delete, export, etc.
    resource_type = Column(String(100))  # candidate, job_listing, application, notification
    resource_id = Column(UUID(as_uuid=True))
    table_name = Column(String(100))

    # Data tracking
    old_data = Column(JSONB)
    new_data = Column(JSONB)
    changes = Column(JSONB)  # Specific fields that changed

    # Request details
    endpoint = Column(String(255))
    http_method = Column(String(10))
    request_data = Column(JSONB)
    response_status = Column(Integer)

    # GDPR compliance
    data_subject_id = Column(String(255))  # To identify whose data was accessed
    legal_basis = Column(String(100))  # GDPR legal basis for processing
    retention_until = Column(
        DateTime,
        default=lambda: datetime.utcnow() + timedelta(days=30),  # 30 days retention
        nullable=False,
        index=True
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "action IN ('create', 'read', 'update', 'delete', 'export', 'process', 'notify', 'login', 'logout')",
            name='check_action_valid'
        ),
        CheckConstraint(
            "http_method IN ('GET', 'POST', 'PUT', 'PATCH', 'DELETE')",
            name='check_http_method_valid'
        ),
        Index('idx_audit_logs_session_id', 'session_id'),
        Index('idx_audit_logs_resource', 'resource_type', 'resource_id'),
        Index('idx_audit_logs_retention', 'retention_until'),
        Index('idx_audit_logs_data_subject', 'data_subject_id'),
    )

    def to_dict(self) -> Dict:
        """Convert to dictionary for API responses"""
        return {
            'id': str(self.id),
            'session_id': self.session_id,
            'user_id': self.user_id,
            'ip_address': self.ip_address,
            'action': self.action,
            'resource_type': self.resource_type,
            'resource_id': str(self.resource_id) if self.resource_id else None,
            'table_name': self.table_name,
            'endpoint': self.endpoint,
            'http_method': self.http_method,
            'response_status': self.response_status,
            'data_subject_id': self.data_subject_id,
            'legal_basis': self.legal_basis,
        }


class CandidateSession(Base, UUIDMixin, TimestampMixin):
    """
    Tracks candidate sessions for GDPR compliance and session management.
    
    This model stores session information for candidates, including login/logout times,
    IP addresses, and user agents. It helps with security auditing and compliance.
    """
    __tablename__ = 'candidate_sessions'
    
    # Foreign key to the Candidate model
    candidate_id = Column(UUID(as_uuid=True), ForeignKey('candidates.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Session information
    session_token = Column(String(255), unique=True, nullable=False, index=True)
    ip_address = Column(String(45), nullable=False)
    user_agent = Column(Text)
    device_info = Column(JSONB)
    
    # Session timestamps
    login_at = Column(DateTime, default=func.now(), nullable=False)
    last_activity_at = Column(DateTime, default=func.now(), nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    logout_at = Column(DateTime)
    
    # Session status
    is_active = Column(Boolean, default=True, index=True)
    logout_reason = Column(String(100))
    
    # GDPR compliance
    gdpr_consent = Column(Boolean, default=False)
    gdpr_consent_version = Column(String(50))
    gdpr_consent_date = Column(DateTime)
    
    # Relationships
    candidate = relationship("Candidate", back_populates="sessions")
    
    __table_args__ = (
        Index('idx_candidate_sessions_token', 'session_token', unique=True),
        Index('idx_candidate_sessions_active', 'is_active', 'expires_at'),
        Index('idx_candidate_sessions_candidate', 'candidate_id', 'is_active'),
        Index('idx_candidate_sessions_compound', 'is_active', 'expires_at')
    )
    
    def is_expired(self) -> bool:
        """Check if the session has expired."""
        return datetime.utcnow() > self.expires_at
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            'id': str(self.id),
            'candidate_id': str(self.candidate_id),
            'login_at': self.login_at.isoformat() if self.login_at else None,
            'last_activity_at': self.last_activity_at.isoformat() if self.last_activity_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'logout_at': self.logout_at.isoformat() if self.logout_at else None,
            'is_active': self.is_active,
            'ip_address': self.ip_address,
            'device_info': self.device_info or {},
            'gdpr_consent': self.gdpr_consent,
            'gdpr_consent_version': self.gdpr_consent_version,
            'gdpr_consent_date': self.gdpr_consent_date.isoformat() if self.gdpr_consent_date else None,
        }

# Add relationship to Candidate model
Candidate.sessions = relationship(
    "CandidateSession", 
    back_populates="candidate",
    cascade="all, delete-orphan",
    lazy="dynamic"
)

# Indexes for performance optimization
Index('idx_candidates_compound', Candidate.status, Candidate.expires_at)
Index('idx_applications_compound', Application.status, Application.response_deadline, Application.match_score)
Index('idx_notifications_compound', Notification.delivery_status, Notification.sent_at)
Index('idx_audit_logs_compound', AuditLog.action, AuditLog.created_at)
Index('idx_candidate_sessions_compound', CandidateSession.is_active, CandidateSession.expires_at)