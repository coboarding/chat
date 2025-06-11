"""
GDPR compliance endpoints for the coBoarding API.
"""
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException
import aioredis

from app.utils.gdpr_compliance import GDPRManager
from ..dependencies import get_redis

router = APIRouter()


@router.delete("/user-data/{session_id}", response_model=Dict[str, Any])
async def delete_user_data(
    session_id: str,
    redis: aioredis.Redis = Depends(get_redis)
):
    """
    Delete all user data (Right to erasure).
    
    Args:
        session_id: Session ID to delete data for
        redis: Redis client dependency
        
    Returns:
        Dict: Deletion results
    """
    # Check if session exists
    cv_data_exists = await redis.exists(f"cv:{session_id}")
    if not cv_data_exists:
        raise HTTPException(status_code=404, detail="User data not found")
    
    try:
        # Initialize GDPR manager
        gdpr_manager = GDPRManager()
        
        # Delete user data
        deleted_keys = await gdpr_manager.delete_user_data(session_id, redis)
        
        return {
            "session_id": session_id,
            "deleted_keys": deleted_keys,
            "success": True,
            "message": f"Successfully deleted {len(deleted_keys)} data items"
        }
        
    except Exception as e:
        return {
            "session_id": session_id,
            "deleted_keys": [],
            "success": False,
            "message": f"Error deleting user data: {str(e)}"
        }


@router.get("/compliance-report", response_model=Dict[str, Any])
async def gdpr_compliance_report():
    """
    Generate GDPR compliance report.
    
    Returns:
        Dict: GDPR compliance report
    """
    try:
        # Initialize GDPR manager
        gdpr_manager = GDPRManager()
        
        # Generate compliance report
        report = await gdpr_manager.generate_compliance_report()
        
        return {
            "report": report,
            "success": True,
            "timestamp": report.get("timestamp")
        }
        
    except Exception as e:
        return {
            "report": {},
            "success": False,
            "message": f"Error generating compliance report: {str(e)}"
        }
