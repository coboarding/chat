"""
Job matching endpoints for the coBoarding API.
"""
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, Form, Depends, HTTPException
import aioredis

from ..models import JobMatchResponse
from ..dependencies import get_redis

router = APIRouter()


@router.post("/match", response_model=JobMatchResponse)
async def match_jobs(
    session_id: str = Form(...),
    include_remote: bool = Form(True),
    location_preference: Optional[str] = Form(None),
    redis: aioredis.Redis = Depends(get_redis)
):
    """
    Match CV with available job listings.
    
    Args:
        session_id: Session ID from CV upload
        include_remote: Whether to include remote jobs
        location_preference: Preferred job location
        redis: Redis client dependency
        
    Returns:
        JobMatchResponse: Job matching results
    """
    # Get CV data from Redis
    cv_data_str = await redis.get(f"cv:{session_id}")
    if not cv_data_str:
        raise HTTPException(status_code=404, detail="CV data not found")
    
    import ast
    cv_data = ast.literal_eval(cv_data_str)
    
    # Load job listings
    job_listings = await load_job_listings()
    
    # Record start time for metrics
    start_time = datetime.utcnow()
    
    # Match CV with jobs
    matches = await match_cv_with_jobs(cv_data, job_listings)
    
    # Filter by location preference if provided
    if location_preference:
        matches = [
            job for job in matches 
            if location_preference.lower() in job.get("location", "").lower()
        ]
    
    # Include remote jobs if requested
    if include_remote:
        remote_jobs = [job for job in matches if job.get("remote", False)]
        # Add remote jobs not already in matches
        remote_job_ids = [job["id"] for job in matches]
        matches.extend([job for job in remote_jobs if job["id"] not in remote_job_ids])
    
    # Calculate processing time
    processing_time = (datetime.utcnow() - start_time).total_seconds()
    
    return JobMatchResponse(
        matches=matches,
        total_matches=len(matches),
        processing_time=processing_time,
        match_criteria={
            "include_remote": include_remote,
            "location_preference": location_preference
        }
    )


async def load_job_listings() -> List[Dict]:
    """
    Load job listings from JSON file.
    
    Returns:
        List[Dict]: List of job listings
    """
    # In a production environment, this would load from a database
    job_file = os.path.join(os.getcwd(), "data", "job_listings.json")
    
    if not os.path.exists(job_file):
        # Create sample data if file doesn't exist
        sample_jobs = [
            {
                "id": "job1",
                "company": "Tech Innovators",
                "position": "Senior Python Developer",
                "required_skills": ["Python", "FastAPI", "SQL", "Docker"],
                "preferred_skills": ["AWS", "Kubernetes", "React"],
                "location": "Berlin, Germany",
                "remote": True
            },
            {
                "id": "job2",
                "company": "Data Solutions",
                "position": "Data Scientist",
                "required_skills": ["Python", "Pandas", "Machine Learning", "SQL"],
                "preferred_skills": ["PyTorch", "TensorFlow", "Cloud Computing"],
                "location": "Munich, Germany",
                "remote": False
            }
        ]
        
        os.makedirs(os.path.dirname(job_file), exist_ok=True)
        with open(job_file, "w") as f:
            json.dump(sample_jobs, f, indent=2)
    
    with open(job_file, "r") as f:
        return json.load(f)


async def match_cv_with_jobs(cv_data: Dict, job_listings: List[Dict]) -> List[Dict]:
    """
    AI-powered matching between CV and jobs.
    
    Args:
        cv_data: Processed CV data
        job_listings: List of job listings
        
    Returns:
        List[Dict]: Matched job listings with scores
    """
    matches = []
    
    # Extract skills from CV
    cv_skills = set(cv_data.get("skills", []))
    
    for job in job_listings:
        # Get required and preferred skills
        required_skills = set(job.get("required_skills", []))
        preferred_skills = set(job.get("preferred_skills", []))
        
        # Calculate match scores
        required_match = len(cv_skills.intersection(required_skills)) / max(len(required_skills), 1)
        preferred_match = len(cv_skills.intersection(preferred_skills)) / max(len(preferred_skills), 1)
        
        # Calculate overall score (required skills weighted more)
        overall_score = (required_match * 0.7) + (preferred_match * 0.3)
        
        # Add to matches if score is above threshold
        if overall_score > 0.3:  # Arbitrary threshold
            job_copy = job.copy()
            job_copy["match_score"] = round(overall_score, 2)
            job_copy["matched_skills"] = list(cv_skills.intersection(required_skills.union(preferred_skills)))
            job_copy["missing_skills"] = list(required_skills.difference(cv_skills))
            matches.append(job_copy)
    
    # Sort by match score (descending)
    matches.sort(key=lambda x: x["match_score"], reverse=True)
    
    return matches
