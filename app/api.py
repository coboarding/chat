# app/api.py
"""
FastAPI backend server for coBoarding platform
Provides REST API endpoints for CV processing, job matching, and communication
"""

import asyncio
import json
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path

from fastapi import (
    FastAPI, 
    HTTPException, 
    Depends, 
    UploadFile, 
    File, 
    Form,
    BackgroundTasks,
    status
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field
import aioredis
from sqlalchemy.ext.asyncio import AsyncSession

# Internal imports
from core.cv_processor import CVProcessor
from core.form_detector import FormDetector
from core.automation_engine import AutomationEngine
from core.chat_interface import ChatInterface
from core.notification_service import NotificationService
from database.connection import get_db_session
from database.models import Candidate, JobListing, Application, Notification
from utils.gdpr_compliance import GDPRManager

# Initialize FastAPI app
app = FastAPI(
    title="coBoarding API",
    description="Speed Hiring Platform for SME Tech Companies",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://localhost:3000"],  # Streamlit + React
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer(auto_error=False)

# Initialize services
cv_processor = CVProcessor()
form_detector = FormDetector()
automation_engine = AutomationEngine()
chat_interface = ChatInterface()
notification_service = NotificationService()
gdpr_manager = GDPRManager()

# Redis connection
redis_client = None

# Pydantic models
class CVUploadResponse(BaseModel):
    session_id: str
    cv_data: Dict[str, Any]
    processing_time: float
    success: bool
    message: str

class JobMatchResponse(BaseModel):
    matches: List[Dict[str, Any]]
    total_matches: int
    processing_time: float
    match_criteria: Dict[str, Any]

class ChatMessage(BaseModel):
    message: str
    company_id: str
    session_id: str

class ChatResponse(BaseModel):
    response: str
    timestamp: str
    session_id: str
    company_id: str

class TechnicalQuestion(BaseModel):
    question: str
    topic: str
    difficulty: str
    expected_answer_length: str

class TechnicalQuestionResponse(BaseModel):
    questions: List[TechnicalQuestion]
    session_id: str
    company_id: str

class NotificationRequest(BaseModel):
    session_id: str
    company_id: str
    message: str
    notification_type: str = "candidate_application"

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    services: Dict[str, str]

# Startup/Shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize connections and services on startup"""
    global redis_client
    try:
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        redis_client = aioredis.from_url(redis_url)
        
        # Test Redis connection
        await redis_client.ping()
        print("✅ Redis connection established")
        
        # Create upload directories
        upload_dir = Path(os.getenv('UPLOAD_DIR', '/app/uploads'))
        upload_dir.mkdir(exist_ok=True)
        
        print("🚀 coBoarding API server started successfully")
        
    except Exception as e:
        print(f"❌ Startup error: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up connections on shutdown"""
    global redis_client
    if redis_client:
        await redis_client.close()
    print("🛑 coBoarding API server shutdown complete")

# Dependency injection
async def get_redis() -> aioredis.Redis:
    """Get Redis client dependency"""
    if not redis_client:
        raise HTTPException(status_code=500, detail="Redis not available")
    return redis_client

def get_session_id() -> str:
    """Generate new session ID"""
    return f"session_{uuid.uuid4().hex[:16]}"

# Authentication (simple bearer token for MVP)
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Simple authentication for API access"""
    if not credentials:
        return None  # Allow anonymous access for MVP
    
    # In production, implement proper JWT validation
    token = credentials.credentials
    if token == os.getenv('API_TOKEN', 'dev_token_123'):
        return {"user_id": "authenticated_user"}
    
    return None

# Health check endpoint
@app.get("/health", response_model=HealthResponse)
@app.get("/healthz", response_model=HealthResponse)  # Kubernetes style
async def health_check(redis: aioredis.Redis = Depends(get_redis)):
    """Health check endpoint for monitoring"""
    services = {}
    
    try:
        # Check Redis
        await redis.ping()
        services["redis"] = "healthy"
    except:
        services["redis"] = "unhealthy"
    
    try:
        # Check Ollama
        import ollama
        client = ollama.Client(host=os.getenv('OLLAMA_URL', 'http://localhost:11434'))
        client.list()
        services["ollama"] = "healthy"
    except:
        services["ollama"] = "unhealthy"
    
    try:
        # Check database (basic connection test)
        from database.connection import test_connection
        await test_connection()
        services["database"] = "healthy"
    except:
        services["database"] = "unhealthy"
    
    all_healthy = all(status == "healthy" for status in services.values())
    
    return HealthResponse(
        status="healthy" if all_healthy else "degraded",
        timestamp=datetime.now().isoformat(),
        services=services
    )

# CV Upload and Processing
@app.post("/api/cv/upload", response_model=CVUploadResponse)
async def upload_cv(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    redis: aioredis.Redis = Depends(get_redis)
):
    """Upload and process CV file"""
    start_time = datetime.now()
    
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")
        
        # Check file size
        max_size = int(os.getenv('MAX_FILE_SIZE', 10485760))  # 10MB default
        if file.size and file.size > max_size:
            raise HTTPException(status_code=413, detail="File too large")
        
        # Check file type
        allowed_types = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain']
        if file.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail="Unsupported file type")
        
        # Generate session ID
        session_id = get_session_id()
        
        # Process CV
        cv_data = await cv_processor.process_cv(file)
        
        if 'error' in cv_data:
            raise HTTPException(status_code=422, detail=f"CV processing failed: {cv_data['error']}")
        
        # Store in Redis with TTL (GDPR compliance)
        await gdpr_manager.store_with_ttl(session_id, cv_data, ttl_hours=24)
        
        # Background task: Log processing metrics
        background_tasks.add_task(log_processing_metrics, session_id, cv_data, start_time)
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return CVUploadResponse(
            session_id=session_id,
            cv_data=cv_data,
            processing_time=processing_time,
            success=True,
            message="CV processed successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"CV upload error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/cv/{session_id}")
async def get_cv_data(session_id: str):
    """Retrieve CV data by session ID"""
    try:
        cv_data = await gdpr_manager.get_data(session_id)
        if not cv_data:
            raise HTTPException(status_code=404, detail="CV data not found or expired")
        
        return {"cv_data": cv_data, "session_id": session_id}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"CV retrieval error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.put("/api/cv/{session_id}")
async def update_cv_data(session_id: str, cv_data: Dict[str, Any]):
    """Update CV data"""
    try:
        await gdpr_manager.update_with_ttl(session_id, cv_data)
        return {"message": "CV data updated successfully", "session_id": session_id}
        
    except Exception as e:
        print(f"CV update error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Job Matching
@app.post("/api/jobs/match", response_model=JobMatchResponse)
async def match_jobs(
    session_id: str = Form(...),
    include_remote: bool = Form(True),
    location_preference: Optional[str] = Form(None)
):
    """Match CV with available job listings"""
    start_time = datetime.now()
    
    try:
        # Get CV data
        cv_data = await gdpr_manager.get_data(session_id)
        if not cv_data:
            raise HTTPException(status_code=404, detail="CV data not found")
        
        # Load job listings
        job_listings = await load_job_listings()
        
        # Apply filters
        filtered_jobs = []
        for job in job_listings:
            if not include_remote and job.get('remote', False):
                continue
            if location_preference and location_preference.lower() not in job.get('location', '').lower():
                continue
            filtered_jobs.append(job)
        
        # AI-powered matching
        matches = await match_cv_with_jobs(cv_data, filtered_jobs)
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return JobMatchResponse(
            matches=matches,
            total_matches=len(matches),
            processing_time=processing_time,
            match_criteria={
                "include_remote": include_remote,
                "location_preference": location_preference,
                "skills_matched": cv_data.get('skills', [])
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Job matching error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Chat Interface
@app.post("/api/chat/message", response_model=ChatResponse)
async def send_chat_message(message_data: ChatMessage):
    """Send chat message and get AI response"""
    try:
        # Get CV data
        cv_data = await gdpr_manager.get_data(message_data.session_id)
        if not cv_data:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Get company data
        company = await get_company_by_id(message_data.company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        
        # Process message
        response = await chat_interface.process_message(
            message_data.message, 
            cv_data, 
            company
        )
        
        return ChatResponse(
            response=response,
            timestamp=datetime.now().isoformat(),
            session_id=message_data.session_id,
            company_id=message_data.company_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Chat message error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/chat/history/{session_id}/{company_id}")
async def get_chat_history(session_id: str, company_id: str):
    """Get chat history for session and company"""
    try:
        # Implementation would retrieve from Redis/Database
        # For MVP, return empty history
        return {"messages": [], "session_id": session_id, "company_id": company_id}
        
    except Exception as e:
        print(f"Chat history error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Technical Questions (Anti-spam)
@app.post("/api/questions/generate", response_model=TechnicalQuestionResponse)
async def generate_technical_questions(
    session_id: str = Form(...),
    company_id: str = Form(...)
):
    """Generate technical validation questions"""
    try:
        # Get CV data
        cv_data = await gdpr_manager.get_data(session_id)
        if not cv_data:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Get company data
        company = await get_company_by_id(company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        
        # Generate questions
        questions_data = await chat_interface.generate_technical_questions(cv_data, company)
        
        questions = [TechnicalQuestion(**q) for q in questions_data]
        
        return TechnicalQuestionResponse(
            questions=questions,
            session_id=session_id,
            company_id=company_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Question generation error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Notifications
@app.post("/api/notifications/send")
async def send_notification(notification_data: NotificationRequest):
    """Send notification to employer about new candidate"""
    try:
        # Get CV data
        cv_data = await gdpr_manager.get_data(notification_data.session_id)
        if not cv_data:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Get company data
        company = await get_company_by_id(notification_data.company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        
        # Send notifications
        results = await notification_service.notify_employer(
            company, 
            cv_data, 
            notification_data.message
        )
        
        return {"notification_results": results, "success": True}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Notification error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Form Automation
@app.post("/api/automation/detect-forms")
async def detect_forms(url: str = Form(...)):
    """Detect forms on a webpage"""
    try:
        fields = await form_detector.detect_forms(url)
        
        return {
            "fields": [
                {
                    "element_id": field.element_id,
                    "field_type": field.field_type,
                    "label": field.label,
                    "required": field.required,
                    "confidence": field.confidence
                }
                for field in fields
            ],
            "total_fields": len(fields),
            "url": url
        }
        
    except Exception as e:
        print(f"Form detection error: {e}")
        raise HTTPException(status_code=500, detail="Form detection failed")

@app.post("/api/automation/fill-forms")
async def fill_forms(
    session_id: str = Form(...),
    url: str = Form(...)
):
    """Automatically fill forms using CV data"""
    try:
        # Get CV data
        cv_data = await gdpr_manager.get_data(session_id)
        if not cv_data:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Fill forms
        results = await automation_engine.fill_forms(cv_data, url)
        
        return results
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Form filling error: {e}")
        raise HTTPException(status_code=500, detail="Form filling failed")

# GDPR Compliance
@app.delete("/api/gdpr/delete/{session_id}")
async def delete_user_data(session_id: str):
    """Delete all user data (Right to erasure)"""
    try:
        deleted = await gdpr_manager.delete_data(session_id)
        
        if deleted:
            return {"message": "Data deleted successfully", "session_id": session_id}
        else:
            raise HTTPException(status_code=404, detail="No data found for this session")
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Data deletion error: {e}")
        raise HTTPException(status_code=500, detail="Data deletion failed")

@app.get("/api/gdpr/report")
async def gdpr_compliance_report():
    """Generate GDPR compliance report"""
    try:
        report = await gdpr_manager.generate_compliance_report()
        return report
        
    except Exception as e:
        print(f"GDPR report error: {e}")
        raise HTTPException(status_code=500, detail="Report generation failed")

# Helper functions
async def load_job_listings() -> List[Dict]:
    """Load job listings from JSON file"""
    try:
        job_listings_path = Path("/app/data/job_listings.json")
        if job_listings_path.exists():
            with open(job_listings_path, 'r') as f:
                return json.load(f)
        return []
    except Exception as e:
        print(f"Error loading job listings: {e}")
        return []

async def match_cv_with_jobs(cv_data: Dict, job_listings: List[Dict]) -> List[Dict]:
    """AI-powered matching between CV and jobs"""
    matches = []
    
    cv_skills = set(skill.lower() for skill in cv_data.get('skills', []))
    cv_title = cv_data.get('title', '').lower()
    
    for job in job_listings:
        # Calculate match score
        job_skills = set(req.lower() for req in job.get('requirements', []))
        skill_overlap = len(cv_skills.intersection(job_skills))
        title_match = any(word in cv_title for word in job['position'].lower().split())
        
        score = (skill_overlap * 0.7) + (title_match * 0.3)
        
        if score > 0:
            matches.append({
                **job,
                'match_score': min(score, 1.0),
                'matching_skills': list(cv_skills.intersection(job_skills))
            })
    
    # Sort by match score
    return sorted(matches, key=lambda x: x['match_score'], reverse=True)

async def get_company_by_id(company_id: str) -> Optional[Dict]:
    """Get company data by ID"""
    job_listings = await load_job_listings()
    for job in job_listings:
        if job.get('id') == company_id:
            return job
    return None

async def log_processing_metrics(session_id: str, cv_data: Dict, start_time: datetime):
    """Background task to log processing metrics"""
    try:
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # Log metrics (could be sent to monitoring system)
        print(f"CV processed: session_id={session_id}, time={processing_time:.2f}s, skills_count={len(cv_data.get('skills', []))}")
        
    except Exception as e:
        print(f"Metrics logging error: {e}")

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"detail": "Resource not found", "timestamp": datetime.now().isoformat()}
    )

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "timestamp": datetime.now().isoformat()}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        reload=True if os.getenv('ENVIRONMENT') == 'development' else False
    )