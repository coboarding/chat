"""
Data models for the coBoarding application.
"""

# Import from the new modular structure
from app.core.models import (
    CVData,
    CompanyProfile,
    ChatMessage,
    Notification,
    MatchResult,
    JobApplication,
    ModelType
)

# Re-export all models
__all__ = [
    'CVData',
    'CompanyProfile',
    'ChatMessage',
    'Notification',
    'MatchResult',
    'JobApplication',
    'ModelType'
]
