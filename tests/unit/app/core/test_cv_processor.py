"""Tests for CVProcessor class."""
"""Tests for CVProcessor class."""
import os
import io
import json
import pytest
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

import pytest_asyncio
from app.core.cv_processor import CVProcessor

@pytest.fixture
def mock_uploaded_file():
    """Create a mock uploaded file."""
    file_mock = MagicMock()
    file_mock.name = "test_cv.pdf"
    file_mock.type = "application/pdf"
    file_mock.read.return_value = b"%PDF-test-pdf-content"
    file_mock.tell.return_value = 0  # Add tell() method for file pointer position
    file_mock.seek = MagicMock()  # Add seek() method
    return file_mock

@pytest.fixture
def cv_processor():
    """Create a CVProcessor instance with mocked Ollama client."""
    processor = CVProcessor(test_mode=True)  # Enable test mode
    processor.ollama_client = MagicMock()
    processor.ollama_client.chat = AsyncMock()
    return processor

@pytest.mark.asyncio
async def test_process_cv_success(cv_processor, mock_uploaded_file):
    """Test successful CV processing."""
    # Mock file operations and methods
    with patch('builtins.open', mock_open()) as mock_file, \
         patch('pathlib.Path.mkdir'), \
         patch('pathlib.Path.exists', return_value=True), \
         patch('PyPDF2.PdfReader') as mock_pdf_reader, \
         patch.object(cv_processor, '_extract_text', return_value="Test CV content") as mock_extract:
        
        # Call the method
        result = await cv_processor.process_cv(mock_uploaded_file)
        
        # Assertions - should return test mode data
        assert result["name"] == "Test User"
        assert "Python" in result["skills"]
        assert result["experience"][0]["position"] == "Test Engineer"
        assert "file_path" in result
        
        # Verify mocks were called
        mock_extract.assert_called_once()

@pytest.mark.asyncio
async def test_extract_pdf_text(cv_processor):
    """Test PDF text extraction."""
    test_pdf = Path("test.pdf")
    
    with patch('builtins.open', mock_open()) as mock_file, \
         patch('PyPDF2.PdfReader') as mock_pdf_reader:
        
        # Mock PDF reader
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Test PDF content"
        mock_pdf_reader.return_value.pages = [mock_page]
        
        # Call the method
        result = await cv_processor._extract_pdf_text(test_pdf)
        
        # Assertions
        assert result == "Test PDF content"
        mock_pdf_reader.assert_called_once()

@pytest.mark.asyncio
async def test_process_with_mistral(cv_processor):
    """Test CV processing with Mistral model."""
    test_text = "John Doe\nPython Developer"
    
    # Test with test mode (should return test data)
    result = await cv_processor._process_with_mistral(test_text)
    assert result["name"] == "Test User"
    assert "Python" in result["skills"]
    
    # Test with mock Ollama client
    cv_processor.test_mode = False
    expected_response = {
        "message": {
            "content": json.dumps({
                "name": "John Doe",
                "email": "john@example.com",
                "title": "Python Developer",
                "skills": ["Python", "Docker"]
            })
        }
    }
    
    cv_processor.ollama_client.chat.return_value = expected_response
    
    # Call the method
    result = await cv_processor._process_with_mistral(test_text)
    
    # Assertions
    assert result["name"] == "John Doe"
    assert "Python" in result["skills"]
    cv_processor.ollama_client.chat.assert_called_once()
    
    # Test with already parsed JSON
    expected_response["message"]["content"] = {"name": "Parsed JSON"}
    cv_processor.ollama_client.chat.return_value = expected_response
    result = await cv_processor._process_with_mistral(test_text)
    assert result["name"] == "Parsed JSON"
    
    # Test with invalid JSON response
    expected_response["message"]["content"] = "invalid json"
    result = await cv_processor._process_with_mistral(test_text)
    assert result == {}

@pytest.mark.asyncio
async def test_merge_extraction_results(cv_processor):
    """Test merging results from different extraction methods."""
    results = [
        {"name": "John Doe", "skills": ["Python"]},
        {"name": "John Doe", "skills": ["Docker"], "email": "john@example.com"},
        {"title": "Developer"}
    ]
    
    # Call the method directly
    merged = await cv_processor._merge_extraction_results(results, "")
    
    # Assertions
    assert merged["name"] == "John Doe"
    assert set(merged["skills"]) == {"Python", "Docker"}
    assert merged["email"] == "john@example.com"
    assert merged["title"] == "Developer"
