"""
FastAPI REST API for document extraction
"""

import asyncio
import os
from pathlib import Path
from typing import Dict, Any, List, Optional

import uvicorn
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from docextract.core.processor import DocumentProcessor
from docextract.utils.config import Config, ExtractionMethod


# Create FastAPI app
app = FastAPI(
    title="DocExtract API",
    description="API for extracting data from documents using multiple LLM models",
    version="0.1.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ExtractionResponse(BaseModel):
    """Response model for extraction endpoints"""
    success: bool
    data: Dict[str, Any]
    method: str
    file_info: Dict[str, Any]


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "DocExtract API",
        "version": "0.1.0",
        "description": "API for extracting data from documents using multiple LLM models",
    }


@app.get("/config")
async def get_config():
    """Get current configuration"""
    return Config.to_dict()


@app.get("/methods")
async def get_methods():
    """Get available extraction methods"""
    return {
        "methods": [method.value for method in ExtractionMethod],
        "default": Config.EXTRACTION_METHOD.value,
    }


@app.post("/extract", response_model=ExtractionResponse)
async def extract_document(
    file: UploadFile = File(...),
    method: Optional[str] = Query(None, description="Extraction method to use"),
):
    """Extract data from document
    
    Args:
        file: Document file
        method: Extraction method to use (optional)
        
    Returns:
        Extracted data
    """
    try:
        # Validate extraction method
        extraction_method = None
        if method:
            try:
                extraction_method = ExtractionMethod(method)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid extraction method: {method}. Available methods: {[m.value for m in ExtractionMethod]}",
                )
        
        # Create document processor
        processor = DocumentProcessor(extraction_method)
        
        # Process file
        content = await file.read()
        data = await processor.process_bytes(content, file.filename)
        
        return ExtractionResponse(
            success=True,
            data=data,
            method=processor.extraction_method.value,
            file_info={
                "filename": file.filename,
                "content_type": file.content_type,
                "size": len(content),
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/extract/batch", response_model=List[ExtractionResponse])
async def extract_batch(
    files: List[UploadFile] = File(...),
    method: Optional[str] = Query(None, description="Extraction method to use"),
):
    """Extract data from multiple documents
    
    Args:
        files: List of document files
        method: Extraction method to use (optional)
        
    Returns:
        List of extracted data
    """
    try:
        # Validate extraction method
        extraction_method = None
        if method:
            try:
                extraction_method = ExtractionMethod(method)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid extraction method: {method}. Available methods: {[m.value for m in ExtractionMethod]}",
                )
        
        # Create document processor
        processor = DocumentProcessor(extraction_method)
        
        # Process files in parallel
        results = []
        for file in files:
            content = await file.read()
            data = await processor.process_bytes(content, file.filename)
            
            results.append(
                ExtractionResponse(
                    success=True,
                    data=data,
                    method=processor.extraction_method.value,
                    file_info={
                        "filename": file.filename,
                        "content_type": file.content_type,
                        "size": len(content),
                    },
                )
            )
        
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def start_api():
    """Start the API server"""
    uvicorn.run(
        "docextract.api.main:app",
        host=Config.API_HOST,
        port=Config.API_PORT,
        reload=Config.DEBUG,
    )


if __name__ == "__main__":
    start_api()
