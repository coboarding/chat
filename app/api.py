"""
FastAPI backend server for coBoarding platform
Provides REST API endpoints for CV processing, job matching, and communication
"""

# Import the app from the modular API structure
from app.api.main import app

# Re-export the app for backward compatibility
__all__ = ['app']

# This file is maintained for backward compatibility
# All functionality has been moved to the modular structure in app/api/
