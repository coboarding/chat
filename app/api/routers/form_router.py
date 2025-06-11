"""
Form automation endpoints for the coBoarding API.
"""
from typing import Dict, Any, List

from fastapi import APIRouter, Form, Depends, HTTPException
import aioredis

from app.core.form_detector import FormDetector
from app.core.automation_engine import AutomationEngine
from ..dependencies import get_redis

router = APIRouter()


@router.post("/detect", response_model=Dict[str, Any])
async def detect_forms(url: str = Form(...)):
    """
    Detect forms on a webpage.
    
    Args:
        url: URL of the webpage to analyze
        
    Returns:
        Dict: Detected form elements
    """
    try:
        # Initialize form detector
        form_detector = FormDetector()
        
        # Detect forms on the webpage
        forms = await form_detector.detect_forms(url=url)
        
        return {
            "url": url,
            "forms": forms,
            "total_forms": len(forms),
            "success": True,
            "message": f"Detected {len(forms)} forms on the webpage"
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "url": url,
            "forms": [],
            "total_forms": 0,
            "success": False,
            "message": f"Error detecting forms: {str(e)}"
        }


@router.post("/fill", response_model=Dict[str, Any])
async def fill_forms(
    session_id: str = Form(...),
    url: str = Form(...),
    redis: aioredis.Redis = Depends(get_redis)
):
    """
    Automatically fill forms using CV data.
    
    Args:
        session_id: Session ID from CV upload
        url: URL of the webpage with forms to fill
        redis: Redis client dependency
        
    Returns:
        Dict: Form filling results
    """
    # Get CV data from Redis
    cv_data_str = await redis.get(f"cv:{session_id}")
    if not cv_data_str:
        raise HTTPException(status_code=404, detail="CV data not found")
    
    import ast
    cv_data = ast.literal_eval(cv_data_str)
    
    try:
        # Initialize automation engine
        automation_engine = AutomationEngine()
        
        # Fill forms on the webpage
        results = await automation_engine.fill_forms(url=url, cv_data=cv_data)
        
        return {
            "url": url,
            "session_id": session_id,
            "fields_filled": results["fields_filled"],
            "total_fields": results["total_fields"],
            "success": True,
            "message": f"Filled {results['fields_filled']} out of {results['total_fields']} fields"
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "url": url,
            "session_id": session_id,
            "fields_filled": 0,
            "total_fields": 0,
            "success": False,
            "message": f"Error filling forms: {str(e)}"
        }
