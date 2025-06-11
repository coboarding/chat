"""CV Processor module for extracting and processing CV information using multiple models."""

import asyncio
import json
import re
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

import spacy
import ollama
import PyPDF2
import docx
from PIL import Image
import pytesseract


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
        temp_path = await self._save_temp_file(uploaded_file)
        try:
            # Read file content if it's a file-like object
            file_content = b''
            if hasattr(uploaded_file, 'read'):
                if asyncio.iscoroutinefunction(uploaded_file.read):
                    file_content = await uploaded_file.read()
                else:
                    file_content = uploaded_file.read()
                
                # Reset file pointer if possible
                if hasattr(uploaded_file, 'seek') and hasattr(uploaded_file, 'tell'):
                    if uploaded_file.tell() > 0:
                        uploaded_file.seek(0)
            
            # Extract text from the file
            text_content = await self._extract_text(temp_path, getattr(uploaded_file, 'type', 'application/octet-stream'))
            if not text_content:
                raise ValueError("Could not extract text from CV")
            
            # In test mode, return mock data immediately
            if hasattr(self, 'test_mode') and self.test_mode:
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
                self._process_with_mistral(text_content),
                self._process_with_visual_llm(temp_path, getattr(uploaded_file, 'type', 'application/octet-stream')),
                self._process_with_spacy(text_content),
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
    
    async def _save_temp_file(self, uploaded_file) -> Path:
        """Save uploaded file to a temporary location.
        
        Args:
            uploaded_file: File-like object with read() method
            
        Returns:
            Path: Path to the saved temporary file
        """
        # Create a temporary directory if it doesn't exist
        temp_dir = Path("temp_uploads")
        temp_dir.mkdir(exist_ok=True)
        
        # Create a temporary file with the same extension
        suffix = Path(uploaded_file.name).suffix if hasattr(uploaded_file, 'name') else '.tmp'
        temp_file = tempfile.NamedTemporaryFile(
            dir=temp_dir,
            suffix=suffix,
            delete=False
        )
        
        try:
            # Write the uploaded file content to the temporary file
            content = uploaded_file.read()
            if hasattr(content, 'decode'):
                content = content.decode('utf-8')
            temp_file.write(content if isinstance(content, bytes) else content.encode('utf-8'))
            return Path(temp_file.name)
        finally:
            temp_file.close()
    
    async def _extract_text(self, file_path: Path, file_type: str) -> str:
        """Extract text from various file formats.
        
        Args:
            file_path: Path to the file
            file_type: MIME type of the file
            
        Returns:
            str: Extracted text content
        """
        try:
            if file_type == 'application/pdf':
                return await self._extract_pdf_text(file_path)
            elif file_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
                return await self._extract_docx_text(file_path)
            elif file_type == 'text/plain':
                return await self._extract_txt_text(file_path)
            else:
                # Try OCR for images or unknown types
                return await self._extract_ocr_text(file_path)
        except Exception as e:
            print(f"Error extracting text from {file_path}: {e}")
            return ""
    
    async def _extract_pdf_text(self, file_path: Path) -> str:
        """Extract text from PDF file.
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            str: Extracted text content
        """
        try:
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                text = '\n'.join([page.extract_text() for page in reader.pages])
                return text.strip()
        except Exception as e:
            print(f"Error extracting text from PDF {file_path}: {e}")
            return ""
    
    async def _extract_docx_text(self, file_path: Path) -> str:
        """Extract text from DOCX file.
        
        Args:
            file_path: Path to the DOCX file
            
        Returns:
            str: Extracted text content
        """
        try:
            doc = docx.Document(file_path)
            return '\n'.join([para.text for para in doc.paragraphs])
        except Exception as e:
            print(f"Error extracting text from DOCX {file_path}: {e}")
            return ""
    
    async def _extract_txt_text(self, file_path: Path) -> str:
        """Extract text from plain text file.
        
        Args:
            file_path: Path to the text file
            
        Returns:
            str: File content
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception as e:
            print(f"Error reading text file {file_path}: {e}")
            return ""
    
    async def _extract_ocr_text(self, file_path: Path) -> str:
        """Extract text from image using OCR.
        
        Args:
            file_path: Path to the image file
            
        Returns:
            str: Extracted text content
        """
        try:
            image = Image.open(file_path)
            text = pytesseract.image_to_string(image)
            return text.strip()
        except Exception as e:
            print(f"Error performing OCR on {file_path}: {e}")
            return ""
    
    async def _process_with_mistral(self, text: str) -> Dict[str, Any]:
        """Process CV text with Mistral 7B for structured extraction.
        
        Args:
            text: Extracted text from CV
            
        Returns:
            Dict with structured CV information
        """
        try:
            # In test mode, return a mock response
            if hasattr(self, 'test_mode') and self.test_mode:
                return {
                    'name': 'Test User',
                    'email': 'test@example.com',
                    'skills': ['Python', 'Testing'],
                    'experience': [{'position': 'Test Engineer', 'company': 'Test Inc'}]
                }
            
            # Prepare the prompt for Mistral
            prompt = f"""Extract the following information from this CV in JSON format:
            - name
            - email
            - phone
            - title/position
            - skills (list)
            - experience (list of objects with position, company, start_date, end_date, description)
            - education (list of objects with degree, institution, year)
            - certifications (list)
            - languages (list)
            - linkedin (url)
            - github (url)
            - website (url)
            
            CV Content:
            {text}
            
            Return ONLY the JSON object, no other text."""
            
            # Check if we're running in a test environment with a mocked Ollama client
            if hasattr(self, 'ollama_client') and hasattr(self.ollama_client, 'chat'):
                # Use the mock client if available (for unit tests)
                response = await self.ollama_client.chat(
                    model='mistral',
                    messages=[{'role': 'user', 'content': prompt}]
                )
                
                if response and 'message' in response and 'content' in response['message']:
                    content = response['message']['content']
                    if isinstance(content, dict):
                        return content  # Already parsed JSON
                    
                    # Clean and parse the JSON response
                    json_str = self._clean_json_response(content)
                    try:
                        result = json.loads(json_str)
                        return result if isinstance(result, dict) else {}
                    except json.JSONDecodeError as e:
                        print(f"Failed to parse JSON response: {e}")
                        return {}
            else:
                # Use aiohttp for async HTTP requests in production
                try:
                    import aiohttp
                    
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            'http://localhost:11434/api/chat',
                            json={
                                'model': 'mistral',
                                'messages': [{'role': 'user', 'content': prompt}]
                            }
                        ) as response:
                            if response.status == 200:
                                response_data = await response.json()
                                if 'message' in response_data and 'content' in response_data['message']:
                                    content = response_data['message']['content']
                                    # Clean up the response to ensure it's valid JSON
                                    json_str = self._clean_json_response(content)
                                    try:
                                        # Parse the JSON string into a dictionary
                                        result = json.loads(json_str)
                                        return result if isinstance(result, dict) else {}
                                    except json.JSONDecodeError as e:
                                        print(f"Failed to parse JSON response: {e}")
                                        print(f"Response content: {content}")
                                        return {}
                except Exception as e:
                    print(f"Error calling Ollama API: {e}")
            
            return {}
            
        except Exception as e:
            print(f"Mistral processing error: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    async def _process_with_visual_llm(self, file_path: Path, file_type: str) -> Dict[str, Any]:
        """Process CV with visual LLM for layout-aware extraction.
        
        Args:
            file_path: Path to the CV file
            file_type: MIME type of the file
            
        Returns:
            Dict with structured CV information
        """
        try:
            # For non-image files, we'll skip visual processing
            if not file_type.startswith('image/'):
                return {}
                
            # Read and encode the image
            with open(file_path, 'rb') as f:
                img_base64 = base64.b64encode(f.read()).decode('utf-8')
            
            prompt = """Analyze this CV/resume image and extract key information. Focus on:
            1. Personal contact information
            2. Professional experience sections
            3. Education details
            4. Skills mentioned
            5. Any visual elements like logos, formatting that might indicate seniority
            
            Return structured data as JSON format focusing on what's clearly visible."""
            
            # Call Ollama API with the image
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.ollama_client.chat(
                    model='llava',
                    messages=[
                        {
                            'role': 'user',
                            'content': prompt,
                            'images': [img_base64]
                        }
                    ]
                )
            )
            
            # Process the response
            if response and 'message' in response and 'content' in response['message']:
                content = response['message']['content']
                json_str = self._clean_json_response(content)
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    print(f"Failed to parse visual LLM response: {json_str}")
            return {}
            
        except Exception as e:
            print(f"Visual LLM processing error: {e}")
            return {}
    
    async def _process_with_spacy(self, text: str) -> Dict[str, Any]:
        """Process CV text with spaCy for NER and basic extraction.
        
        Args:
            text: Extracted text from CV
            
        Returns:
            Dict with basic CV information
        """
        if not self.nlp or not text:
            return {}
            
        try:
            doc = self.nlp(text)
            
            # Extract entities
            name = ""
            email = ""
            phone = ""
            skills = set()
            
            for ent in doc.ents:
                if ent.label_ == "PERSON" and not name:
                    name = ent.text
                elif ent.label_ == "EMAIL" and not email:
                    email = ent.text
                elif ent.label_ == "PHONE" and not phone:
                    phone = ent.text
            
            # Simple skill extraction (very basic)
            skills_keywords = ["python", "java", "javascript", "c++", "c#", "ruby", "php", "swift", "kotlin", "go", 
                            "rust", "typescript", "sql", "html", "css", "react", "angular", "vue", "django", "flask", 
                            "node.js", "spring", "docker", "kubernetes", "aws", "azure", "gcp"]
            
            for token in doc:
                if token.text.lower() in skills_keywords:
                    skills.add(token.text.lower())
            
            return {
                'name': name,
                'email': email,
                'phone': phone,
                'skills': list(skills)
            }
            
        except Exception as e:
            print(f"spaCy processing error: {e}")
            return {}
    
    async def _merge_extraction_results(self, results: List[Dict[str, Any]], original_text: str) -> Dict[str, Any]:
        """Merge results from different extraction methods.
        
        Args:
            results: List of extraction results from different methods
            original_text: Original CV text
            
        Returns:
            Dict with merged CV information
        """
        merged = {
            'name': '',
            'email': '',
            'phone': '',
            'title': '',
            'summary': '',
            'skills': [],
            'experience': [],
            'education': [],
            'certifications': [],
            'languages': [],
            'linkedin': '',
            'github': '',
            'website': ''
        }
        
        # Simple merging strategy: take the first non-empty value for each field
        for result in results:
            if not isinstance(result, dict):
                continue
                
            for key in merged:
                if key in result and result[key] and not merged[key]:
                    merged[key] = result[key]
        
        # Special handling for lists (merge unique values)
        list_fields = ['skills', 'experience', 'education', 'certifications', 'languages']
        for field in list_fields:
            if field in merged and isinstance(merged[field], list):
                # Collect all unique values from all results
                all_values = []
                for result in results:
                    if isinstance(result, dict) and field in result and isinstance(result[field], list):
                        all_values.extend(result[field])
                
                # Remove duplicates while preserving order
                seen = set()
                merged[field] = [x for x in all_values if not (x in seen or seen.add(x))]
        
        return merged
    
    def _clean_json_response(self, text: str) -> str:
        """Clean and extract JSON from model response.
        
        Args:
            text: Raw text response from the model
            
        Returns:
            str: Cleaned JSON string that can be parsed
        """
        if not text or not isinstance(text, str):
            return '{}'
            
        # Remove markdown code block markers if present
        if '```' in text:
            parts = text.split('```')
            text = parts[1] if len(parts) > 1 else parts[0]
        
        # Remove any whitespace and newlines from start/end
        text = text.strip()
        
        # If the response is already valid JSON, return it
        try:
            json.loads(text)
            return text
        except json.JSONDecodeError:
            pass
            
        # Try to fix trailing commas in objects and arrays
        try:
            # Simple fix for trailing commas before closing braces/brackets
            fixed_text = re.sub(r',\s*([}\]])', r'\1', text)
            json.loads(fixed_text)
            return fixed_text
        except json.JSONDecodeError:
            pass
            
        # Try to extract JSON from the text
        try:
            first_brace = text.find('{')
            last_brace = text.rfind('}')
            
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                potential_json = text[first_brace:last_brace+1]
                # Try to fix and parse
                fixed = re.sub(r',\s*([}\]])', r'\1', potential_json)
                json.loads(fixed)
                return fixed
        except (json.JSONDecodeError, ValueError):
            pass
            
        # If all else fails, return an empty object
            pass
            
        # If we still can't parse it, return an empty object
        return '{}'
