"""LLM-based CV processing functionality."""

import json
import re
from typing import Dict, Any, Optional

import ollama


def clean_json_response(response_text: str) -> str:
    """Clean LLM response to extract valid JSON.
    
    Args:
        response_text: Raw text response from LLM
        
    Returns:
        str: Cleaned JSON string
    """
    # Find JSON content between triple backticks or code blocks
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
    if json_match:
        return json_match.group(1).strip()
    
    # Look for content that appears to be JSON (starting with { and ending with })
    json_match = re.search(r'(\{[\s\S]*\})', response_text)
    if json_match:
        return json_match.group(1).strip()
    
    # If no JSON-like content found, return the original text
    return response_text.strip()


async def process_with_mistral(text: str, ollama_client=None, test_mode: bool = False) -> Dict[str, Any]:
    """Process CV text with Mistral 7B for structured extraction.
    
    Args:
        text: Extracted text from CV
        ollama_client: Ollama client instance
        test_mode: If True, returns mock data
        
    Returns:
        Dict with structured CV information
    """
    try:
        # In test mode, return a mock response
        if test_mode:
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
        
        # Check if we're running with a provided Ollama client
        if ollama_client and hasattr(ollama_client, 'chat'):
            # Use the ollama client - note that chat() is not an async method
            response = ollama_client.chat(
                model='mistral',
                messages=[{'role': 'user', 'content': prompt}]
            )
            
            if response and 'message' in response and 'content' in response['message']:
                content = response['message']['content']
                if isinstance(content, dict):
                    return content  # Already parsed JSON
                
                # Clean and parse the JSON response
                json_str = clean_json_response(content)
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
                                json_str = clean_json_response(content)
                                try:
                                    # Parse the JSON string into a dictionary
                                    result = json.loads(json_str)
                                    return result if isinstance(result, dict) else {}
                                except json.JSONDecodeError as e:
                                    print(f"Failed to parse JSON response: {e}")
                                    print(f"Response content: {content}")
                                    return {}
            except ImportError:
                print("aiohttp not available for async HTTP requests")
                return {}
    except Exception as e:
        print(f"Error processing with Mistral: {e}")
        return {}


async def process_with_visual_llm(file_path, file_type: str, ollama_client=None, test_mode: bool = False) -> Dict[str, Any]:
    """Process CV with visual LLM (LLaVA) for multimodal extraction.
    
    Args:
        file_path: Path to the CV file
        file_type: MIME type of the file
        ollama_client: Ollama client instance
        test_mode: If True, returns mock data
        
    Returns:
        Dict with structured CV information
    """
    try:
        # In test mode, return a mock response
        if test_mode:
            return {
                'name': 'Visual Test User',
                'skills': ['UI/UX', 'Design'],
                'experience': [{'position': 'Designer', 'company': 'Design Co'}]
            }
            
        # Convert PDF to image if needed
        if file_type == 'application/pdf':
            try:
                import fitz  # PyMuPDF
                import base64
                from PIL import Image
                import io
                
                # Open the PDF
                doc = fitz.open(file_path)
                
                # Get the first page
                page = doc.load_page(0)
                
                # Render page to an image (pix is a PyMuPDF Pixmap)
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                
                # Convert to PIL Image
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                
                # Convert to base64
                buffered = io.BytesIO()
                img.save(buffered, format="JPEG")
                img_base64 = base64.b64encode(buffered.getvalue()).decode()
                
                # Close the document
                doc.close()
                
                # Use LLaVA for visual analysis
                if ollama_client:
                    prompt = """Analyze this CV image and extract the following information in JSON format:
                    - name
                    - skills (list)
                    - experience (list of objects with position, company)
                    - education (list of objects with degree, institution)
                    
                    Return ONLY the JSON object, no other text."""
                    
                    response = ollama_client.generate(
                        model='llava',
                        prompt=prompt,
                        images=[img_base64]
                    )
                    
                    if response and 'response' in response:
                        # Clean and parse the JSON response
                        json_str = clean_json_response(response['response'])
                        try:
                            result = json.loads(json_str)
                            return result if isinstance(result, dict) else {}
                        except json.JSONDecodeError:
                            return {}
            except ImportError as e:
                print(f"Error converting PDF to image: {e}")
                return {}
        
        return {}
    except Exception as e:
        print(f"Error processing with visual LLM: {e}")
        return {}


async def process_with_spacy(text: str, nlp=None, test_mode: bool = False) -> Dict[str, Any]:
    """Process CV text with spaCy for named entity recognition.
    
    Args:
        text: Extracted text from CV
        nlp: spaCy NLP model
        test_mode: If True, returns mock data
        
    Returns:
        Dict with structured CV information
    """
    try:
        # In test mode, return a mock response
        if test_mode:
            return {
                'name': 'SpaCy Test User',
                'organizations': ['Test Corp', 'Example Inc'],
                'locations': ['New York', 'San Francisco'],
                'dates': ['2020-2022', '2018-2020']
            }
            
        if not nlp:
            return {}
            
        # Process the text with spaCy
        doc = nlp(text)
        
        # Extract entities
        entities = {
            'name': '',
            'organizations': [],
            'locations': [],
            'dates': [],
            'skills': []
        }
        
        # Extract named entities
        for ent in doc.ents:
            if ent.label_ == 'PERSON':
                if not entities['name']:  # Take the first person as the CV owner
                    entities['name'] = ent.text
            elif ent.label_ == 'ORG':
                if ent.text not in entities['organizations']:
                    entities['organizations'].append(ent.text)
            elif ent.label_ == 'GPE' or ent.label_ == 'LOC':
                if ent.text not in entities['locations']:
                    entities['locations'].append(ent.text)
            elif ent.label_ == 'DATE':
                if ent.text not in entities['dates']:
                    entities['dates'].append(ent.text)
        
        # Extract skills (simple keyword matching)
        skill_keywords = [
            'python', 'javascript', 'java', 'c++', 'c#', 'react', 'angular', 'vue', 
            'node', 'django', 'flask', 'express', 'sql', 'nosql', 'mongodb', 'postgresql',
            'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'ci/cd', 'git', 'agile', 'scrum'
        ]
        
        text_lower = text.lower()
        for skill in skill_keywords:
            if skill in text_lower:
                entities['skills'].append(skill)
        
        return entities
    except Exception as e:
        print(f"Error processing with spaCy: {e}")
        return {}
