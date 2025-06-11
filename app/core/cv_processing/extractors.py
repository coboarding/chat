"""Text extraction functionality for different file formats."""

import asyncio
from pathlib import Path

import PyPDF2
import docx
from PIL import Image
import pytesseract


async def extract_text(file_path: Path, file_type: str) -> str:
    """Extract text from various file formats.
    
    Args:
        file_path: Path to the file
        file_type: MIME type of the file
        
    Returns:
        str: Extracted text content
    """
    try:
        if file_type == 'application/pdf':
            return await extract_pdf_text(file_path)
        elif file_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
            return await extract_docx_text(file_path)
        elif file_type == 'text/plain':
            return await extract_txt_text(file_path)
        else:
            # Try OCR for images or unknown types
            return await extract_ocr_text(file_path)
    except Exception as e:
        print(f"Error extracting text from {file_path}: {e}")
        return ""


async def extract_pdf_text(file_path: Path) -> str:
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


async def extract_docx_text(file_path: Path) -> str:
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


async def extract_txt_text(file_path: Path) -> str:
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


async def extract_ocr_text(file_path: Path) -> str:
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
