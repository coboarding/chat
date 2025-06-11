import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import json

from app.core.cv_processor import CVProcessor

@pytest.fixture
def cv_processor():
    return CVProcessor()

@pytest.mark.asyncio
async def test_process_cv_with_pdf(cv_processor, tmp_path):
    # Create a mock PDF file
    pdf_path = tmp_path / "test_cv.pdf"
    pdf_path.write_text("""
    John Doe
    Senior Software Engineer
    Skills: Python, Docker, Kubernetes
    Experience: 5+ years
    """)
    
    # Mock the file upload
    class MockUploadedFile:
        def __init__(self, file_path, content_type):
            self.file_path = file_path
            self.type = content_type
        
        async def read(self):
            with open(self.file_path, 'rb') as f:
                return f.read()
    
    uploaded_file = MockUploadedFile(pdf_path, "application/pdf")
    
    # Mock the response from Ollama
    mock_response = {
        "message": {
            "content": json.dumps({
                "name": "John Doe",
                "title": "Senior Software Engineer",
                "skills": ["Python", "Docker", "Kubernetes"],
                "experience": [{"position": "Senior Software Engineer", "years": 5}]
            })
        }
    }
    
    with patch('app.core.cv_processor.ollama.Client') as mock_ollama:
        mock_ollama.return_value.chat.return_value = mock_response
        
        # Process the CV
        result = await cv_processor.process_cv(uploaded_file)
        
        # Assert the result
        assert "name" in result
        assert result["name"] == "John Doe"
        assert "skills" in result
        assert "Python" in result["skills"]
        assert "experience" in result
        assert len(result["experience"]) > 0

@pytest.mark.asyncio
async def test_process_with_mistral(cv_processor):
    # Mock the Ollama client
    mock_response = {
        "message": {
            "content": json.dumps({
                "name": "Jane Smith",
                "title": "Data Scientist",
                "skills": ["Python", "Machine Learning", "Data Analysis"],
                "experience": [{"position": "Data Scientist", "years": 3}]
            })
        }
    }
    
    with patch('app.core.cv_processor.ollama.Client') as mock_ollama:
        mock_ollama.return_value.chat.return_value = mock_response
        
        # Process the text with Mistral
        result = await cv_processor._process_with_mistral("Jane Smith\nData Scientist\nSkills: Python, ML")
        
        # Assert the result
        assert "name" in result
        assert result["name"] == "Jane Smith"
        assert "skills" in result
        assert "Python" in result["skills"]
        assert "experience" in result
        assert len(result["experience"]) > 0

def test_clean_json_response(cv_processor):
    # Test with malformed JSON
    malformed_json = '{"name": "John", "age": 30,}'
    cleaned = cv_processor._clean_json_response(malformed_json)
    assert json.loads(cleaned) == {"name": "John", "age": 30}
    
    # Test with valid JSON
    valid_json = '{"name": "John", "age": 30}'
    assert cv_processor._clean_json_response(valid_json) == valid_json
