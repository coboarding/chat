"""
API router modules for the coBoarding platform.
"""

from . import (
    cv_router,
    job_router,
    chat_router,
    form_router,
    gdpr_router,
    health_router
)

__all__ = [
    'cv_router',
    'job_router',
    'chat_router',
    'form_router',
    'gdpr_router',
    'health_router'
]
