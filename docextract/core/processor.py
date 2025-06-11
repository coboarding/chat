"""
Document processor module for handling file operations and extraction
"""

import asyncio
import os
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, Union, BinaryIO

from docextract.core.extractor import BaseExtractor, ExtractorFactory, HybridExtractor
from docextract.utils.config import Config, ExtractionMethod


class DocumentProcessor:
    """Document processor for handling file operations and extraction"""
    
    def __init__(self, extraction_method: ExtractionMethod = None):
        """Initialize document processor
        
        Args:
            extraction_method: Method to use for extraction
        """
        self.extraction_method = extraction_method or Config.EXTRACTION_METHOD
        
        # Create extractor based on method
        if self.extraction_method == ExtractionMethod.HYBRID:
            self.extractor = HybridExtractor()
        else:
            self.extractor = ExtractorFactory.create_extractor(self.extraction_method)
        
        # Ensure temp directory exists
        os.makedirs(Config.TEMP_DIR, exist_ok=True)
    
    async def process_file(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """Process document file
        
        Args:
            file_path: Path to document file
            
        Returns:
            Dict with extracted data
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        return await self.extractor.extract(path)
    
    async def process_bytes(self, content: bytes, filename: str = None) -> Dict[str, Any]:
        """Process document from bytes
        
        Args:
            content: Document content as bytes
            filename: Original filename (used for extension)
            
        Returns:
            Dict with extracted data
        """
        # Create temporary file
        suffix = f".{Path(filename).suffix}" if filename else ".tmp"
        fd, temp_path = tempfile.mkstemp(suffix=suffix, dir=Config.TEMP_DIR)
        os.close(fd)
        
        try:
            # Write content to temp file
            with open(temp_path, 'wb') as f:
                f.write(content)
            
            # Process the file
            return await self.process_file(temp_path)
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_path)
            except:
                pass
    
    async def process_stream(self, stream: BinaryIO, filename: str = None) -> Dict[str, Any]:
        """Process document from stream
        
        Args:
            stream: File-like object with read() method
            filename: Original filename (used for extension)
            
        Returns:
            Dict with extracted data
        """
        # Read content from stream
        content = stream.read()
        
        # Process bytes
        return await self.process_bytes(content, filename)
    
    async def process_file_batch(self, file_paths: list[Union[str, Path]]) -> list[Dict[str, Any]]:
        """Process multiple document files in parallel
        
        Args:
            file_paths: List of paths to document files
            
        Returns:
            List of dicts with extracted data
        """
        tasks = [self.process_file(path) for path in file_paths]
        return await asyncio.gather(*tasks)
