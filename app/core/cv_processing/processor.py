"""Main CV processor module that integrates all specialized CV processing modules."""

import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

import spacy
import ollama

from .extractors import extract_text
from .file_utils import save_temp_file, read_file_content
from .llm_processors import process_with_mistral, process_with_visual_llm, process_with_spacy


class CVProcessor:
    """Advanced CV processing with multiple local LLM models."""
    
    def __init__(self, ollama_url: str = "http://localhost:11434", test_mode: bool = False):
        """Initialize the CV processor with Ollama client.
        
        Args:
            ollama_url: URL of the Ollama server (default: http://localhost:11434)
            test_mode: If True, uses mock responses for testing (default: False)
        """
        self.test_mode = test_mode
        if not test_mode:
            self.ollama_client = ollama.Client(host=ollama_url)
        self.nlp = None
        self._load_spacy_model()
    
    def _load_spacy_model(self):
        """Load spaCy model for Named Entity Recognition."""
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            print("Warning: spaCy model not found. Install with: python -m spacy download en_core_web_sm")
            self.nlp = None
    
    async def process_cv(self, uploaded_file) -> dict:
        """Process an uploaded CV file with multiple extraction methods.
        
        Args:
            uploaded_file: File-like object with read() method
            
        Returns:
            dict: Merged results from all extraction methods
        """
        temp_path = await save_temp_file(uploaded_file)
        try:
            # Read file content if it's a file-like object
            file_content = await read_file_content(uploaded_file)
            
            # Extract text from the file
            text_content = await extract_text(temp_path, getattr(uploaded_file, 'type', 'application/octet-stream'))
            if not text_content:
                raise ValueError("Could not extract text from CV")
            
            # In test mode, return mock data immediately
            if self.test_mode:
                return {
                    'name': 'Test User',
                    'email': 'test@example.com',
                    'skills': ['Python', 'Testing'],
                    'experience': [{'position': 'Test Engineer', 'company': 'Test Inc'}],
                    'file_path': str(temp_path),
                    'file_type': getattr(uploaded_file, 'type', 'application/octet-stream'),
                    'file_name': getattr(uploaded_file, 'name', 'unknown')
                }
            
            # Run all extraction methods in parallel
            results = await asyncio.gather(
                process_with_mistral(text_content, self.ollama_client if hasattr(self, 'ollama_client') else None, self.test_mode),
                process_with_visual_llm(temp_path, getattr(uploaded_file, 'type', 'application/octet-stream'), 
                                       self.ollama_client if hasattr(self, 'ollama_client') else None, self.test_mode),
                process_with_spacy(text_content, self.nlp, self.test_mode),
                return_exceptions=True
            )
            
            # Filter out any exceptions
            filtered_results = [r for r in results if not isinstance(r, Exception)]
            
            # Merge all results
            final_result = await self._merge_extraction_results(filtered_results, text_content)
            
            # Ensure we have the required fields
            if not isinstance(final_result, dict):
                final_result = {}
                
            # Add file metadata
            final_result['file_path'] = str(temp_path)
            final_result['file_type'] = getattr(uploaded_file, 'type', 'application/octet-stream')
            final_result['file_name'] = getattr(uploaded_file, 'name', 'unknown')
            final_result['processed_at'] = asyncio.get_event_loop().time()
            
            # Ensure required fields exist
            final_result.setdefault('name', 'Unknown')
            final_result.setdefault('skills', [])
            final_result.setdefault('experience', [])
            
            return final_result
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                'error': str(e),
                'file_path': str(temp_path) if 'temp_path' in locals() else None,
                'name': 'Unknown',
                'skills': [],
                'experience': []
            }
    
    async def _merge_extraction_results(self, results: List[Dict[str, Any]], original_text: str) -> Dict[str, Any]:
        """Merge results from different extraction methods.
        
        Args:
            results: List of dictionaries with extraction results
            original_text: Original text content from CV
            
        Returns:
            dict: Merged results
        """
        if not results:
            return {}
            
        # Start with the most comprehensive result (usually from Mistral)
        merged = {}
        
        # Find the most comprehensive result to use as base
        base_result = None
        max_keys = 0
        
        for result in results:
            if isinstance(result, dict) and len(result.keys()) > max_keys:
                max_keys = len(result.keys())
                base_result = result
                
        if base_result:
            merged = base_result.copy()
            
        # Merge in data from other results
        for result in results:
            if result is base_result or not isinstance(result, dict):
                continue
                
            # Merge simple fields if missing in merged result
            for key, value in result.items():
                if key not in merged or not merged[key]:
                    merged[key] = value
                elif isinstance(value, list) and isinstance(merged[key], list):
                    # For lists (like skills), add unique items
                    for item in value:
                        if item not in merged[key]:
                            merged[key].append(item)
                            
        # Post-process the merged result
        return self._post_process_result(merged, original_text)
    
    def _post_process_result(self, result: Dict[str, Any], original_text: str) -> Dict[str, Any]:
        """Post-process the merged result to improve quality.
        
        Args:
            result: Merged extraction results
            original_text: Original text content from CV
            
        Returns:
            dict: Post-processed results
        """
        # Ensure lists are actually lists
        for key in ['skills', 'experience', 'education', 'certifications', 'languages']:
            if key in result and not isinstance(result[key], list):
                if isinstance(result[key], str):
                    # Try to convert string representation of list to actual list
                    try:
                        import ast
                        result[key] = ast.literal_eval(result[key])
                    except (SyntaxError, ValueError):
                        result[key] = [result[key]]
                else:
                    result[key] = []
        
        # Extract email if missing
        if ('email' not in result or not result['email']) and original_text:
            import re
            email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', original_text)
            if email_match:
                result['email'] = email_match.group(0)
                
        # Extract phone if missing
        if ('phone' not in result or not result['phone']) and original_text:
            import re
            # Look for various phone formats
            phone_patterns = [
                r'\+\d{1,3}\s?\(\d{1,4}\)\s?\d{3,4}[-\s]?\d{3,4}',  # +1 (123) 456-7890
                r'\+\d{1,3}\s?\d{1,4}\s?\d{3,4}\s?\d{3,4}',          # +1 123 456 7890
                r'\(\d{3,4}\)\s?\d{3,4}[-\s]?\d{3,4}',               # (123) 456-7890
                r'\d{3,4}[-\s]?\d{3,4}[-\s]?\d{3,4}'                 # 123-456-7890
            ]
            
            for pattern in phone_patterns:
                phone_match = re.search(pattern, original_text)
                if phone_match:
                    result['phone'] = phone_match.group(0)
                    break
        
        return result
