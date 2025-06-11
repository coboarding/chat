"""
Configuration module for DocExtract
"""

import os
from enum import Enum
from typing import Optional, Dict, Any
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class ExtractionMethod(str, Enum):
    """Supported document extraction methods"""
    MISTRAL = "mistral"
    LLAVA = "llava"
    LLAVA_NEXT = "llava_next"
    QWEN = "qwen"
    SPACY = "spacy"
    OCR = "ocr"
    HYBRID = "hybrid"  # Uses multiple methods and merges results


class Config:
    """Configuration class for DocExtract"""
    
    # Default extraction method
    DEFAULT_EXTRACTION_METHOD = ExtractionMethod.HYBRID
    
    # Ollama API URL
    OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
    
    # Model mappings
    MODEL_MAPPINGS = {
        ExtractionMethod.MISTRAL: os.getenv("MISTRAL_MODEL", "mistral:7b-instruct"),
        ExtractionMethod.LLAVA: os.getenv("LLAVA_MODEL", "llava:7b"),
        ExtractionMethod.LLAVA_NEXT: os.getenv("LLAVA_NEXT_MODEL", "llava:next"),
        ExtractionMethod.QWEN: os.getenv("QWEN_MODEL", "qwen:7b"),
    }
    
    # Extraction method to use (from .env or default)
    EXTRACTION_METHOD = ExtractionMethod(os.getenv("EXTRACTION_METHOD", DEFAULT_EXTRACTION_METHOD.value))
    
    # Temp directory for file processing
    TEMP_DIR = Path(os.getenv("TEMP_DIR", "/tmp/docextract"))
    
    # API settings
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", "8000"))
    
    # Spacy model
    SPACY_MODEL = os.getenv("SPACY_MODEL", "en_core_web_sm")
    
    # Enable debug mode
    DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")
    
    @classmethod
    def get_model_for_method(cls, method: ExtractionMethod) -> str:
        """Get the model name for a specific extraction method"""
        return cls.MODEL_MAPPINGS.get(method, cls.MODEL_MAPPINGS[ExtractionMethod.MISTRAL])
    
    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """Convert config to dictionary"""
        return {
            "extraction_method": cls.EXTRACTION_METHOD,
            "ollama_api_url": cls.OLLAMA_API_URL,
            "model_mappings": cls.MODEL_MAPPINGS,
            "temp_dir": str(cls.TEMP_DIR),
            "api_host": cls.API_HOST,
            "api_port": cls.API_PORT,
            "spacy_model": cls.SPACY_MODEL,
            "debug": cls.DEBUG,
        }
