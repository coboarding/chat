# app/core/__init__.py
"""
Core AI components for coBoarding platform
Provides CV processing, form automation, and chat functionality
"""

from .cv_processor import CVProcessor
from .form_detector import FormDetector, FormField, DetectionMethod
from .form_detector import AutomationEngine
from .chat_interface import ChatInterface
from .notification_service import NotificationService

# Import database models from the database package
from app.database.models import (
    Base,
    Candidate,
    JobListing,
    Application,
    Notification as DBNotification,  # Rename to avoid conflict
    AuditLog,
    TimestampMixin,
    UUIDMixin
)

__all__ = [
    'CVProcessor',
    'FormDetector',
    'FormField',
    'DetectionMethod',
    'AutomationEngine',
    'ChatInterface',
    'NotificationService',
    'Base',
    'Candidate',
    'JobListing',
    'Application',
    'DBNotification',
    'AuditLog',
    'TimestampMixin',
    'UUIDMixin'
]

__version__ = '1.0.0'
from app.database.connection import (
    init_database,
    close_database,
    get_db_session,
    get_session,
    test_connection,
    create_candidate,
    get_candidate_by_session,
    get_active_job_listings,
    create_application,
    get_pending_notifications
)

__all__ = [
    # Models
    'Base',
    'Candidate',
    'JobListing',
    'Application',
    'Notification',
    'AuditLog',
    'TimestampMixin',
    'UUIDMixin',

    # Connection utilities
    'init_database',
    'close_database',
    'get_db_session',
    'get_session',
    'test_connection',

    # Database operations
    'create_candidate',
    'get_candidate_by_session',
    'get_active_job_listings',
    'create_application',
    'get_pending_notifications'
]

__version__ = '1.0.0'
