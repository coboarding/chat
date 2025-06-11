"""Tests for the CV Processor integration."""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open, AsyncMock

from app.core.cv_processor import CVProcessor

@pytest.fixture
def cv_processor():
    """Create a CVProcessor instance with test_mode=True."""
    processor = CVProcessor(test_mode=True)
    return processor

@pytest.fixture
def mock_uploaded_file():
    """Create a mock uploaded file."""
    file_content = b"""
    John Doe
    Senior Software Engineer
    Skills: Python, Docker, Kubernetes
    Experience: 5+ years
    """
    
    mock_file = MagicMock()
    mock_file.read.return_value = file_content
    mock_file.name = "test_cv.pdf"
    mock_file.type = "application/pdf"
    mock_file.tell.return_value = 0
    mock_file.seek = MagicMock()
    return mock_file

@pytest.mark.asyncio
async def test_process_cv_with_pdf(cv_processor, mock_uploaded_file, tmp_path):
    """Test processing a CV with a PDF file."""
    # Set up mocks for file operations
    with patch('builtins.open', mock_open()) as mock_file, \
         patch('pathlib.Path.mkdir'), \
         patch('pathlib.Path.exists', return_value=True), \
         patch('PyPDF2.PdfReader') as mock_pdf_reader:
        
        # Mock PDF reader to return some text
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "John Doe\nSenior Software Engineer\nSkills: Python, Docker, Kubernetes\nExperience: 5+ years"
        mock_pdf_reader.return_value.pages = [mock_page]
        
        # Process the CV
        result = await cv_processor.process_cv(mock_uploaded_file)
        
        # Assert the result
        assert "name" in result
        assert result["name"] == "Test User"  # From our test_mode response
        assert "skills" in result
        assert "experience" in result
        assert len(result["experience"]) > 0

@pytest.mark.asyncio
async def test_process_with_mistral(cv_processor):
    """Test processing with Mistral model."""
    # Test with test mode enabled (should return mock data)
    result = await cv_processor._process_with_mistral("Jane Smith\nData Scientist\nSkills: Python, ML")
    
    # Assert the result matches our test_mode response
    assert "name" in result
    assert result["name"] == "Test User"
    assert "skills" in result
    assert "experience" in result
    
    # Test with test mode disabled and mock Ollama client
    cv_processor.test_mode = False
    cv_processor.ollama_client = AsyncMock()
    cv_processor.ollama_client.chat.return_value = {
        "message": {
            "content": json.dumps({
                "name": "Jane Smith",
                "title": "Data Scientist",
                "skills": ["Python", "Machine Learning"],
                "experience": [{"position": "Data Scientist", "company": "Test Inc"}]
            })
        }
    }
    
    result = await cv_processor._process_with_mistral("Jane Smith\nData Scientist\nSkills: Python, ML")
    
    assert "name" in result
    assert result["name"] == "Jane Smith"
    assert "skills" in result

def test_clean_json_response(cv_processor):
    """Test cleaning JSON responses from the LLM."""
    # Test with malformed JSON
    malformed_json = '{"name": "John", "age": 30,}'
    cleaned = cv_processor._clean_json_response(malformed_json)
    assert json.loads(cleaned) == {"name": "John", "age": 30}
    
    # Test with valid JSON
    valid_json = '{"name": "John", "age": 30}'
    assert cv_processor._clean_json_response(valid_json) == valid_json
    
    # Test with JSON that has extra text around it
    wrapped_json = 'Some text before {\"name\": \"John\"} and after'
    cleaned = cv_processor._clean_json_response(wrapped_json)
    assert json.loads(cleaned) == {"name": "John"}
    
    # Test with code block markers
    code_block_json = '```json\n{"name": "John"}\n```'
    cleaned = cv_processor._clean_json_response(code_block_json)
    assert json.loads(cleaned) == {"name": "John"}
