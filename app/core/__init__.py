# app/core/__init__.py
"""
Core AI components for coBoarding platform
Provides CV processing, form automation, and chat functionality
"""

from .cv_processor import CVProcessor
from .form_detector import FormDetector, FormField, DetectionMethod
from .automation_engine import AutomationEngine
from .chat_interface import ChatInterface
from .notification_service import NotificationService

__all__ = [
    'CVProcessor',
    'FormDetector',
    'FormField',
    'DetectionMethod',
    'AutomationEngine',
    'ChatInterface',
    'NotificationService'
]

__version__ = '1.0.0'

# ===================================================================

# app/database/__init__.py
"""
Database layer for coBoarding platform
Provides models, connections, and utilities for data persistence
"""

from .models import (
    Base,
    Candidate,
    JobListing,
    Application,
    Notification,
    AuditLog,
    TimestampMixin,
    UUIDMixin
)
from .connection import (
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

# ===================================================================

# app/utils/__init__.py
"""
Utility modules for coBoarding platform
Provides GDPR compliance, validation, and helper functions
"""

from .gdpr_compliance import GDPRManager

__all__ = [
    'GDPRManager'
]

__version__ = '1.0.0'

# ===================================================================

# worker/core/__init__.py
"""
Worker core components for background task processing
"""

from .automation_worker import AutomationWorker

__all__ = [
    'AutomationWorker'
]

__version__ = '1.0.0'

# ===================================================================

# worker/utils/__init__.py
"""
Worker utility modules
Provides configuration, task queue, and monitoring
"""

from .helpers import WorkerConfig, TaskQueue, HealthMonitor

__all__ = [
    'WorkerConfig',
    'TaskQueue',
    'HealthMonitor'
]

__version__ = '1.0.0'

# ===================================================================

# cleanup/scripts/__init__.py
"""
Cleanup scripts for GDPR compliance and maintenance
"""

__all__ = []
__version__ = '1.0.0'