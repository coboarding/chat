"""
Chat interface endpoints for the coBoarding API.
"""
from datetime import datetime
from typing import Dict, List, Any

from fastapi import APIRouter, Depends, HTTPException
import aioredis

from app.core.chat_interface import ChatInterface
from ..models import ChatMessage, ChatResponse, TechnicalQuestion, TechnicalQuestionResponse
from ..dependencies import get_redis

router = APIRouter()


@router.post("/message", response_model=ChatResponse)
async def send_chat_message(
    message_data: ChatMessage,
    redis: aioredis.Redis = Depends(get_redis)
):
    """
    Send chat message and get AI response.
    
    Args:
        message_data: Chat message data
        redis: Redis client dependency
        
    Returns:
        ChatResponse: AI response to the message
    """
    # Get CV data for context
    cv_data_str = await redis.get(f"cv:{message_data.session_id}")
    if not cv_data_str:
        raise HTTPException(status_code=404, detail="CV data not found")
    
    import ast
    cv_data = ast.literal_eval(cv_data_str)
    
    # Get company data
    company_data = await get_company_by_id(message_data.company_id)
    
    # Initialize chat interface
    chat_interface = ChatInterface()
    
    # Process message and get response
    response = await chat_interface.process_message(
        message=message_data.message,
        session_id=message_data.session_id,
        company_id=message_data.company_id,
        cv_data=cv_data,
        company_data=company_data
    )
    
    # Store chat history in Redis
    chat_history_key = f"chat:{message_data.session_id}:{message_data.company_id}"
    
    # Get existing history or initialize empty list
    history_str = await redis.get(chat_history_key)
    history = ast.literal_eval(history_str) if history_str else []
    
    # Add new messages to history
    history.append({
        "role": "user",
        "message": message_data.message,
        "timestamp": datetime.utcnow().isoformat()
    })
    history.append({
        "role": "assistant",
        "message": response,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    # Store updated history with 24-hour expiry
    await redis.setex(chat_history_key, 86400, str(history))
    
    return ChatResponse(
        response=response,
        timestamp=datetime.utcnow().isoformat(),
        session_id=message_data.session_id,
        company_id=message_data.company_id
    )


@router.get("/history/{session_id}/{company_id}", response_model=List[Dict[str, Any]])
async def get_chat_history(
    session_id: str,
    company_id: str,
    redis: aioredis.Redis = Depends(get_redis)
):
    """
    Get chat history for session and company.
    
    Args:
        session_id: Session ID
        company_id: Company ID
        redis: Redis client dependency
        
    Returns:
        List[Dict]: Chat history
    """
    chat_history_key = f"chat:{session_id}:{company_id}"
    history_str = await redis.get(chat_history_key)
    
    if not history_str:
        return []
    
    import ast
    return ast.literal_eval(history_str)


@router.post("/technical-questions", response_model=TechnicalQuestionResponse)
async def generate_technical_questions(
    session_id: str,
    company_id: str,
    redis: aioredis.Redis = Depends(get_redis)
):
    """
    Generate technical validation questions.
    
    Args:
        session_id: Session ID
        company_id: Company ID
        redis: Redis client dependency
        
    Returns:
        TechnicalQuestionResponse: Generated technical questions
    """
    # Get CV data for context
    cv_data_str = await redis.get(f"cv:{session_id}")
    if not cv_data_str:
        raise HTTPException(status_code=404, detail="CV data not found")
    
    import ast
    cv_data = ast.literal_eval(cv_data_str)
    
    # Get company data
    company_data = await get_company_by_id(company_id)
    
    # Initialize chat interface
    chat_interface = ChatInterface()
    
    # Generate questions based on CV skills and company requirements
    skills = cv_data.get("skills", [])
    required_skills = company_data.get("required_skills", [])
    
    # Find skills that match between CV and job requirements
    matching_skills = [skill for skill in skills if skill in required_skills]
    
    # Generate questions for up to 3 matching skills
    questions = []
    for skill in matching_skills[:3]:
        questions.append(
            TechnicalQuestion(
                question=f"Please explain your experience with {skill}.",
                topic=skill,
                difficulty="medium",
                expected_answer_length="paragraph"
            )
        )
    
    # Add a general question if we have fewer than 3 matching skills
    if len(questions) < 3:
        questions.append(
            TechnicalQuestion(
                question="What makes you interested in this position?",
                topic="motivation",
                difficulty="easy",
                expected_answer_length="paragraph"
            )
        )
    
    return TechnicalQuestionResponse(
        questions=questions,
        session_id=session_id,
        company_id=company_id
    )


async def get_company_by_id(company_id: str) -> Dict[str, Any]:
    """
    Get company data by ID.
    
    Args:
        company_id: Company ID
        
    Returns:
        Dict: Company data
    """
    # In a production environment, this would query a database
    # For now, return mock data
    return {
        "id": company_id,
        "name": "Example Company",
        "required_skills": ["Python", "FastAPI", "React"],
        "preferred_skills": ["Docker", "AWS", "TypeScript"]
    }
