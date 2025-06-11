"""
Core document extraction module with support for multiple LLMs
"""

import asyncio
import base64
import json
import os
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, BinaryIO

import ollama
import PyPDF2
import docx
import spacy
from PIL import Image
import pytesseract

from docextract.utils.config import Config, ExtractionMethod


class BaseExtractor(ABC):
    """Base class for document extractors"""
    
    @abstractmethod
    async def extract(self, file_path: Path) -> Dict[str, Any]:
        """Extract data from document"""
        pass
    
    @staticmethod
    async def _extract_text(file_path: Path) -> str:
        """Extract text from document based on file type"""
        suffix = file_path.suffix.lower()
        
        if suffix == '.pdf':
            return await BaseExtractor._extract_pdf_text(file_path)
        elif suffix in ['.docx', '.doc']:
            return await BaseExtractor._extract_docx_text(file_path)
        elif suffix in ['.txt', '.md', '.rst']:
            return await BaseExtractor._extract_text_file(file_path)
        else:
            # Try OCR for unknown file types
            return await BaseExtractor._extract_ocr_text(file_path)
    
    @staticmethod
    async def _extract_pdf_text(file_path: Path) -> str:
        """Extract text from PDF file"""
        try:
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                text = '\n'.join([page.extract_text() or '' for page in reader.pages])
                return text.strip()
        except Exception as e:
            print(f"Error extracting text from PDF {file_path}: {e}")
            return ""
    
    @staticmethod
    async def _extract_docx_text(file_path: Path) -> str:
        """Extract text from DOCX file"""
        try:
            doc = docx.Document(file_path)
            text = '\n'.join([para.text for para in doc.paragraphs])
            return text.strip()
        except Exception as e:
            print(f"Error extracting text from DOCX {file_path}: {e}")
            return ""
    
    @staticmethod
    async def _extract_text_file(file_path: Path) -> str:
        """Extract text from plain text file"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                return f.read().strip()
        except Exception as e:
            print(f"Error extracting text from file {file_path}: {e}")
            return ""
    
    @staticmethod
    async def _extract_ocr_text(file_path: Path) -> str:
        """Extract text using OCR"""
        try:
            image = Image.open(file_path)
            text = pytesseract.image_to_string(image)
            return text.strip()
        except Exception as e:
            print(f"Error extracting text with OCR from {file_path}: {e}")
            return ""
    
    @staticmethod
    def _clean_json_response(text: str) -> str:
        """Clean LLM response to ensure it's valid JSON"""
        # Find JSON block in markdown if present
        json_match = json.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if json_match:
            text = json_match.group(1)
        
        # Remove any non-JSON text before or after
        start_idx = text.find('{')
        end_idx = text.rfind('}')
        
        if start_idx != -1 and end_idx != -1:
            text = text[start_idx:end_idx + 1]
        
        return text


class MistralExtractor(BaseExtractor):
    """Document extractor using Mistral LLM"""
    
    def __init__(self, model_name: str = None):
        """Initialize Mistral extractor
        
        Args:
            model_name: Name of the Mistral model to use
        """
        self.model_name = model_name or Config.get_model_for_method(ExtractionMethod.MISTRAL)
        self.ollama_client = ollama.Client(host=Config.OLLAMA_API_URL)
    
    async def extract(self, file_path: Path) -> Dict[str, Any]:
        """Extract data from document using Mistral
        
        Args:
            file_path: Path to document file
            
        Returns:
            Dict with extracted data
        """
        # Extract text from document
        text = await self._extract_text(file_path)
        if not text:
            return {}
        
        # Prepare prompt for Mistral
        prompt = f"""Extract the following information from this CV/resume in JSON format:
        
        - name (string)
        - email (string)
        - phone (string)
        - location (string)
        - current_title (string)
        - years_experience (number)
        - skills (list of strings)
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
        
        try:
            # Use the Ollama client
            response = self.ollama_client.chat(
                model=self.model_name,
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
        except Exception as e:
            print(f"Error processing with Mistral: {e}")
            return {}


class LLaVAExtractor(BaseExtractor):
    """Document extractor using LLaVA visual language model"""
    
    def __init__(self, model_name: str = None):
        """Initialize LLaVA extractor
        
        Args:
            model_name: Name of the LLaVA model to use
        """
        self.model_name = model_name or Config.get_model_for_method(ExtractionMethod.LLAVA)
        self.ollama_client = ollama.Client(host=Config.OLLAMA_API_URL)
    
    async def extract(self, file_path: Path) -> Dict[str, Any]:
        """Extract data from document using LLaVA
        
        Args:
            file_path: Path to document file
            
        Returns:
            Dict with extracted data
        """
        try:
            # Convert PDF to images if needed
            if file_path.suffix.lower() == '.pdf':
                # Use first page as image for LLaVA
                image_path = await self._convert_pdf_to_image(file_path)
                if not image_path:
                    return {}
            else:
                image_path = file_path
            
            # Read and encode the image
            with open(image_path, 'rb') as f:
                img_base64 = base64.b64encode(f.read()).decode('utf-8')
            
            # Prepare prompt for LLaVA
            prompt = """Extract all information from this CV/resume document and format as JSON with these fields:
            
            - name (string)
            - email (string)
            - phone (string)
            - location (string)
            - current_title (string)
            - years_experience (number)
            - skills (list of strings)
            - experience (list of objects with position, company, start_date, end_date, description)
            - education (list of objects with degree, institution, year)
            - certifications (list)
            - languages (list)
            - linkedin (url)
            - github (url)
            - website (url)
            
            Return ONLY the JSON object, no other text."""
            
            # Call LLaVA model using Ollama
            response = self.ollama_client.generate(
                model=self.model_name,
                prompt=prompt,
                images=[img_base64]
            )
            
            if response and 'response' in response:
                content = response['response']
                
                # Clean and parse the JSON response
                json_str = self._clean_json_response(content)
                try:
                    result = json.loads(json_str)
                    return result if isinstance(result, dict) else {}
                except json.JSONDecodeError as e:
                    print(f"Failed to parse JSON response: {e}")
                    return {}
            
            return {}
        except Exception as e:
            print(f"Error processing with LLaVA: {e}")
            return {}
    
    @staticmethod
    async def _convert_pdf_to_image(pdf_path: Path) -> Optional[Path]:
        """Convert first page of PDF to image for visual processing"""
        try:
            import fitz  # PyMuPDF
            
            # Create temp file for image
            fd, temp_path = tempfile.mkstemp(suffix='.png')
            os.close(fd)
            
            # Open PDF and convert first page to image
            doc = fitz.open(pdf_path)
            if doc.page_count > 0:
                page = doc[0]
                pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))
                pix.save(temp_path)
                return Path(temp_path)
            
            return None
        except Exception as e:
            print(f"Error converting PDF to image: {e}")
            return None


class QwenExtractor(BaseExtractor):
    """Document extractor using Qwen LLM"""
    
    def __init__(self, model_name: str = None):
        """Initialize Qwen extractor
        
        Args:
            model_name: Name of the Qwen model to use
        """
        self.model_name = model_name or Config.get_model_for_method(ExtractionMethod.QWEN)
        self.ollama_client = ollama.Client(host=Config.OLLAMA_API_URL)
    
    async def extract(self, file_path: Path) -> Dict[str, Any]:
        """Extract data from document using Qwen
        
        Args:
            file_path: Path to document file
            
        Returns:
            Dict with extracted data
        """
        # Extract text from document
        text = await self._extract_text(file_path)
        if not text:
            return {}
        
        # Prepare prompt for Qwen
        prompt = f"""Extract the following information from this CV/resume in JSON format:
        
        - name (string)
        - email (string)
        - phone (string)
        - location (string)
        - current_title (string)
        - years_experience (number)
        - skills (list of strings)
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
        
        try:
            # Use the Ollama client
            response = self.ollama_client.chat(
                model=self.model_name,
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
        except Exception as e:
            print(f"Error processing with Qwen: {e}")
            return {}


class SpacyExtractor(BaseExtractor):
    """Document extractor using spaCy NER"""
    
    def __init__(self, model_name: str = None):
        """Initialize spaCy extractor
        
        Args:
            model_name: Name of the spaCy model to use
        """
        self.model_name = model_name or Config.SPACY_MODEL
        self.nlp = None
        self._load_spacy_model()
    
    def _load_spacy_model(self):
        """Load spaCy model"""
        try:
            import spacy
            self.nlp = spacy.load(self.model_name)
        except Exception as e:
            print(f"Error loading spaCy model: {e}")
            self.nlp = None
    
    async def extract(self, file_path: Path) -> Dict[str, Any]:
        """Extract data from document using spaCy NER
        
        Args:
            file_path: Path to document file
            
        Returns:
            Dict with extracted data
        """
        if not self.nlp:
            return {}
        
        # Extract text from document
        text = await self._extract_text(file_path)
        if not text:
            return {}
        
        try:
            # Process text with spaCy
            doc = self.nlp(text)
            
            # Extract entities
            entities = {}
            for ent in doc.ents:
                if ent.label_ == "PERSON":
                    entities.setdefault("name", ent.text)
                elif ent.label_ == "EMAIL":
                    entities.setdefault("email", ent.text)
                elif ent.label_ == "PHONE":
                    entities.setdefault("phone", ent.text)
                elif ent.label_ == "GPE" or ent.label_ == "LOC":
                    entities.setdefault("location", ent.text)
                elif ent.label_ == "ORG":
                    entities.setdefault("organizations", []).append(ent.text)
                elif ent.label_ == "DATE":
                    entities.setdefault("dates", []).append(ent.text)
                elif ent.label_ == "SKILL":
                    entities.setdefault("skills", []).append(ent.text)
            
            # Extract skills using pattern matching
            skills = []
            for token in doc:
                if token.pos_ == "NOUN" and token.is_alpha and len(token.text) > 2:
                    skills.append(token.text)
            
            if skills:
                entities["skills"] = list(set(entities.get("skills", []) + skills))
            
            return entities
        except Exception as e:
            print(f"Error processing with spaCy: {e}")
            return {}


class ExtractorFactory:
    """Factory for creating document extractors"""
    
    @staticmethod
    def create_extractor(method: ExtractionMethod) -> BaseExtractor:
        """Create extractor based on method
        
        Args:
            method: Extraction method to use
            
        Returns:
            BaseExtractor instance
        """
        if method == ExtractionMethod.MISTRAL:
            return MistralExtractor()
        elif method == ExtractionMethod.LLAVA:
            return LLaVAExtractor()
        elif method == ExtractionMethod.LLAVA_NEXT:
            return LLaVAExtractor(Config.get_model_for_method(ExtractionMethod.LLAVA_NEXT))
        elif method == ExtractionMethod.QWEN:
            return QwenExtractor()
        elif method == ExtractionMethod.SPACY:
            return SpacyExtractor()
        else:
            # Default to Mistral
            return MistralExtractor()


class HybridExtractor(BaseExtractor):
    """Hybrid document extractor that combines results from multiple extractors"""
    
    def __init__(self, methods: List[ExtractionMethod] = None):
        """Initialize hybrid extractor
        
        Args:
            methods: List of extraction methods to use
        """
        self.methods = methods or [
            ExtractionMethod.MISTRAL,
            ExtractionMethod.LLAVA,
            ExtractionMethod.SPACY
        ]
        self.extractors = [ExtractorFactory.create_extractor(method) for method in self.methods]
    
    async def extract(self, file_path: Path) -> Dict[str, Any]:
        """Extract data from document using multiple extractors
        
        Args:
            file_path: Path to document file
            
        Returns:
            Dict with merged extracted data
        """
        # Run all extractors in parallel
        tasks = [extractor.extract(file_path) for extractor in self.extractors]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions
        valid_results = [r for r in results if isinstance(r, dict)]
        
        # Merge results
        return self._merge_results(valid_results)
    
    def _merge_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge results from multiple extractors
        
        Args:
            results: List of extraction results
            
        Returns:
            Dict with merged data
        """
        if not results:
            return {}
        
        # Start with first result
        merged = results[0].copy()
        
        # Merge in other results
        for result in results[1:]:
            for key, value in result.items():
                if key not in merged:
                    # Add missing key
                    merged[key] = value
                elif isinstance(value, list) and isinstance(merged[key], list):
                    # Merge lists
                    merged[key] = list(set(merged[key] + value))
                elif value and not merged[key]:
                    # Replace empty value
                    merged[key] = value
        
        return merged
