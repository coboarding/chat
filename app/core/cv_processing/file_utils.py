"""File utility functions for CV processing."""

import asyncio
import tempfile
from pathlib import Path
from typing import Any


async def save_temp_file(uploaded_file) -> Path:
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
        
        # Handle different file types appropriately
        if hasattr(uploaded_file, 'type') and uploaded_file.type in ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
            # For binary files like PDF and DOCX, write directly as bytes
            if not isinstance(content, bytes):
                if hasattr(content, 'encode'):
                    content = content.encode('utf-8')
            temp_file.write(content)
        else:
            # For text files, try to decode if it's bytes
            if isinstance(content, bytes):
                try:
                    content = content.decode('utf-8')
                except UnicodeDecodeError:
                    # If decoding fails, treat as binary
                    temp_file.write(content)
                    return Path(temp_file.name)
            
            # Write text content
            temp_file.write(content if isinstance(content, bytes) else content.encode('utf-8'))
        return Path(temp_file.name)
    finally:
        temp_file.close()


async def read_file_content(uploaded_file) -> bytes:
    """Read content from a file-like object.
    
    Args:
        uploaded_file: File-like object with read() method
        
    Returns:
        bytes: File content
    """
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
    
    return file_content
