"""Tests for CVProcessor class."""
import os
import io
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from pathlib import Path
import json

import pytest_asyncio
from app.core.cv_processor import CVProcessor

@pytest.fixture
def mock_uploaded_file():
    """Create a mock uploaded file."""
    file_mock = MagicMock()
    file_mock.name = "test_cv.pdf"
    file_mock.type = "application/pdf"
    file_mock.read.return_value = b"%PDF-test-pdf-content"
    return file_mock

@pytest.fixture
def cv_processor():
    """Create a CVProcessor instance with mocked Ollama client."""
    with patch('app.core.cv_processor.ollama.Client') as mock_client:
        processor = CVProcessor()
        processor.ollama_client = mock_client.return_value
        processor.ollama_client.chat = AsyncMock()
        return processor

@pytest.mark.asyncio
async def test_process_cv_success(cv_processor, mock_uploaded_file):
    """Test successful CV processing."""
    # Mock the response from Ollama
    mock_response = {
        "message": {
            "content": json.dumps({
                "name": "John Doe",
                "email": "john@example.com",
                "skills": ["Python", "Docker"],
                "experience": [{"position": "Developer", "company": "Test Inc"}]
            })
        }
    }
    cv_processor.ollama_client.chat.return_value = mock_response
    
    # Mock file operations and methods
    with patch('builtins.open', mock_open()) as mock_file, \
         patch('pathlib.Path.mkdir'), \
         patch('pathlib.Path.exists', return_value=True), \
         patch('PyPDF2.PdfReader') as mock_pdf_reader, \
         patch.object(cv_processor, '_extract_text', return_value="Test CV content") as mock_extract, \
         patch.object(cv_processor, '_process_with_mistral', return_value={
             "name": "John Doe",
             "email": "john@example.com",
             "skills": ["Python", "Docker"],
             "experience": [{"position": "Developer", "company": "Test Inc"}]
         }) as mock_mistral, \
         patch.object(cv_processor, '_process_with_visual_llm', return_value={}) as mock_visual, \
         patch.object(cv_processor, '_process_with_spacy', return_value={}) as mock_spacy:
        
        # Call the method
        result = await cv_processor.process_cv(mock_uploaded_file)
        
        # Assertions
        assert result["name"] == "John Doe"
        assert "Python" in result["skills"]
        assert result["experience"][0]["position"] == "Developer"
        assert "file_path" in result
        
        # Verify mocks were called
        mock_extract.assert_called_once()
        mock_mistral.assert_called_once_with("Test CV content")

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
    expected_response = {
        "name": "John Doe",
        "email": "john@example.com",
        "title": "Python Developer",
        "skills": ["Python", "Docker"]
    }
    
    # Mock the response from Ollama
    mock_response = {
        "message": {
            "content": json.dumps(expected_response)
        }
    }
    
    # Mock the run_in_executor call
    with patch('asyncio.get_event_loop') as mock_loop:
        mock_loop.return_value.run_in_executor.return_value = mock_response
        
        # Call the method
        result = await cv_processor._process_with_mistral(test_text)
        
        # Assertions
        assert result == expected_response
        cv_processor.ollama_client.chat.assert_called_once()
        
        # Test with invalid JSON response
        cv_processor.ollama_client.chat.return_value = {
            "message": {"content": "invalid json"}
        }
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
