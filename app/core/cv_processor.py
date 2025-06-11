# core/cv_processor.py
import asyncio
import json
import re
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any
import spacy
import ollama
import PyPDF2
import docx
from PIL import Image
import pytesseract
import base64
import io

class CVProcessor:
    """Advanced CV processing with multiple local LLM models"""
    
    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.ollama_client = ollama.Client(host=ollama_url)
        self.nlp = None
        self._load_spacy_model()
        
    def _load_spacy_model(self):
        """Load spaCy model for NER"""
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            print("Warning: spaCy model not found. Install with: python -m spacy download en_core_web_sm")
            self.nlp = None

    async def process_cv(self, uploaded_file) -> Dict[str, Any]:
        """Process uploaded CV file with multiple extraction methods"""
        # Save uploaded file temporarily
        temp_path = await self._save_temp_file(uploaded_file)
        
        try:
            # Extract text from file
            text_content = await self._extract_text(temp_path, uploaded_file.type)
            
            if not text_content:
                raise ValueError("Could not extract text from CV")
            
            # Multi-model processing for maximum accuracy
            results = await asyncio.gather(
                self._process_with_mistral(text_content),
                self._process_with_visual_llm(temp_path, uploaded_file.type),
                self._process_with_spacy(text_content),
                return_exceptions=True
            )
            
            # Filter out any exceptions from results
            filtered_results = []
            for result in results:
                if not isinstance(result, Exception):
                    filtered_results.append(result)
                else:
                    print(f"Warning: A CV processing method failed: {result}")
            
            # Merge results from different models
            final_result = await self._merge_extraction_results(filtered_results, text_content)
            
            # Add file metadata
            final_result['file_path'] = str(temp_path)
            final_result['file_type'] = uploaded_file.type
            final_result['file_name'] = uploaded_file.name
            final_result['processed_at'] = asyncio.get_event_loop().time()
            
            return final_result
            
        except Exception as e:
            print(f"Error processing CV: {e}")
            return {'error': str(e), 'file_path': str(temp_path)}

    async def _save_temp_file(self, uploaded_file) -> Path:
        """Save uploaded file to temporary location"""
        temp_dir = Path("uploads")
        temp_dir.mkdir(exist_ok=True)
        
        temp_path = temp_dir / f"cv_{asyncio.get_event_loop().time()}_{uploaded_file.name}"
        
        with open(temp_path, "wb") as f:
            f.write(uploaded_file.read())
        
        return temp_path

    async def _extract_text(self, file_path: Path, file_type: str) -> str:
        """Extract text from various file formats"""
        try:
            if file_type == "application/pdf":
                return await self._extract_pdf_text(file_path)
            elif file_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                return await self._extract_docx_text(file_path)
            elif file_type == "text/plain":
                return await self._extract_txt_text(file_path)
            else:
                # Try OCR for images or unsupported formats
                return await self._extract_ocr_text(file_path)
        except Exception as e:
            print(f"Error extracting text: {e}")
            return ""

    async def _extract_pdf_text(self, file_path: Path) -> str:
        """Extract text from PDF"""
        text = ""
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
        except Exception as e:
            print(f"PDF extraction error: {e}")
            # Fallback to OCR
            text = await self._extract_ocr_text(file_path)
        
        return text.strip()

    async def _extract_docx_text(self, file_path: Path) -> str:
        """Extract text from DOCX"""
        try:
            doc = docx.Document(file_path)
            text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
            return text.strip()
        except Exception as e:
            print(f"DOCX extraction error: {e}")
            return ""

    async def _extract_txt_text(self, file_path: Path) -> str:
        """Extract text from TXT file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read().strip()
        except Exception as e:
            print(f"TXT extraction error: {e}")
            return ""

    async def _extract_ocr_text(self, file_path: Path) -> str:
        """Extract text using OCR (for images or scanned PDFs)"""
        try:
            # Convert PDF to image if needed
            if file_path.suffix.lower() == '.pdf':
                # Use pdf2image if available
                try:
                    from pdf2image import convert_from_path
                    images = convert_from_path(file_path, first_page=1, last_page=3)  # First 3 pages
                    text = ""
                    for img in images:
                        text += pytesseract.image_to_string(img) + "\n"
                    return text.strip()
                except ImportError:
                    print("pdf2image not available for OCR")
                    return ""
            else:
                # Direct image OCR
                image = Image.open(file_path)
                text = pytesseract.image_to_string(image)
                return text.strip()
        except Exception as e:
            print(f"OCR extraction error: {e}")
            return ""
            return {}

    async def _process_with_visual_llm(self, file_path: Path, file_type: str) -> Dict[str, Any]:
        """Process CV with visual LLM (LLaVA) for layout understanding"""
        if file_type != "application/pdf" and not file_type.startswith("image/"):
            return {}  # Skip visual processing for text files
        
        try:
            # Convert to image if PDF
            if file_path.suffix.lower() == '.pdf':
                try:
                    from pdf2image import convert_from_path
                    images = convert_from_path(file_path, first_page=1, last_page=1)
                    if images:
                        img = images[0]
                        # Convert to base64
                        buffer = io.BytesIO()
                        img.save(buffer, format='PNG')
                        img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                    else:
                        return {}
                except ImportError:
                    return {}
            else:
                # Direct image processing
                with open(file_path, 'rb') as f:
                    img_base64 = base64.b64encode(f.read()).decode('utf-8')
            
            prompt = ("Analyze this CV/resume image and extract key information. Focus on:\n"
                     "1. Personal contact information\n"
                     "2. Professional experience sections\n"
                     "3. Education details\n"
                     "4. Skills mentioned\n"
                     "5. Any visual elements like logos, formatting that might indicate seniority\n\n"
                     "Return structured data as JSON format focusing on what's clearly visible.")
            
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.ollama_client.generate(
                    model='llava:7b',
                    prompt=prompt,
                    images=[img_base64],
                    options={'temperature': 0.1}
                )
            )
            
            # Extract structured data from visual analysis
            return self._parse_visual_response(response['response'])
            
        except Exception as e:
            print(f"Visual LLM processing error: {e}")
            return {}

    async def _process_with_spacy(self, text: str) -> Dict[str, Any]:
        """Process CV text with spaCy for NER and pattern matching"""
        if not self.nlp:
            return {}
        
        try:
            doc = self.nlp(text[:1000000])  # Limit text length
            
            extracted = {
                'persons': [],
                'organizations': [],
                'emails': [],
                'phones': [],
                'dates': [],
                'urls': []
            }
            
            # Named Entity Recognition
            for ent in doc.ents:
                if ent.label_ == "PERSON":
                    extracted['persons'].append(ent.text)
                elif ent.label_ == "ORG":
                    extracted['organizations'].append(ent.text)
                elif ent.label_ == "DATE":
                    extracted['dates'].append(ent.text)
            
            # Pattern matching for specific information
            extracted['emails'] = self._extract_emails(text)
            extracted['phones'] = self._extract_phones(text)
            extracted['urls'] = self._extract_urls(text)
            extracted['skills'] = self._extract_skills_patterns(text)
            
            return extracted
            
        except Exception as e:
            print(f"spaCy processing error: {e}")
            return {}

    def _extract_emails(self, text: str) -> List[str]:
        """Extract email addresses using regex"""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        return list(set(re.findall(email_pattern, text)))

    def _extract_phones(self, text: str) -> List[str]:
        """Extract phone numbers using regex"""
        phone_patterns = [
            r'\+?[\d\s\-\(\)]{10,}',
            r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
            r'\b\(\d{3}\)\s?\d{3}[-.]?\d{4}\b'
        ]
        
        phones = []
        for pattern in phone_patterns:
            phones.extend(re.findall(pattern, text))
        
        # Clean and validate phone numbers
        cleaned_phones = []
        for phone in phones:
            cleaned = re.sub(r'[^\d+]', '', phone)
            if len(cleaned) >= 10:
                cleaned_phones.append(phone.strip())
        
        return list(set(cleaned_phones))

    def _extract_urls(self, text: str) -> List[str]:
        """Extract URLs using regex"""
        url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        urls = re.findall(url_pattern, text)
        
        # Also look for common domain patterns
        domain_pattern = r'\b(?:linkedin\.com|github\.com|stackoverflow\.com|portfolio\.)[^\s]+'
        domains = re.findall(domain_pattern, text, re.IGNORECASE)
        
        return list(set(urls + domains))

    def _extract_skills_patterns(self, text: str) -> List[str]:
        """Extract technical skills using pattern matching"""
        # Common technical skills patterns
        tech_skills = [
            # Programming languages
            'Python', 'JavaScript', 'Java', 'C++', 'C#', 'PHP', 'Ruby', 'Go', 'Rust', 'Swift',
            'TypeScript', 'Kotlin', 'Scala', 'R', 'MATLAB', 'SQL', 'HTML', 'CSS',
            
            # Frameworks and libraries
            'React', 'Angular', 'Vue', 'Django', 'Flask', 'FastAPI', 'Spring', 'Laravel',
            'Express', 'Node.js', 'jQuery', 'Bootstrap', 'TensorFlow', 'PyTorch', 'Pandas',
            'NumPy', 'Scikit-learn', 'Keras', 'OpenCV',
            
            # Databases
            'PostgreSQL', 'MySQL', 'MongoDB', 'Redis', 'Elasticsearch', 'SQLite', 'Oracle',
            'SQL Server', 'Cassandra', 'DynamoDB',
            
            # Cloud and DevOps
            'AWS', 'Azure', 'GCP', 'Docker', 'Kubernetes', 'Jenkins', 'Git', 'CI/CD',
            'Terraform', 'Ansible', 'Linux', 'Ubuntu', 'CentOS',
            
            # Other technologies
            'REST API', 'GraphQL', 'Microservices', 'Machine Learning', 'AI', 'Deep Learning',
            'Data Science', 'Big Data', 'Apache Spark', 'Hadoop', 'Kafka'
        ]
        
        found_skills = []
        text_lower = text.lower()
        
        for skill in tech_skills:
            if skill.lower() in text_lower:
                found_skills.append(skill)
        
        return found_skills

    def _parse_visual_response(self, response: str) -> Dict[str, Any]:
        """Parse visual LLM response into structured data"""
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            
            # Fallback to pattern extraction
            visual_data = {}
            
            # Extract key information using patterns
            if 'email' in response.lower():
                emails = self._extract_emails(response)
                if emails:
                    visual_data['email'] = emails[0]
            
            if 'phone' in response.lower():
                phones = self._extract_phones(response)
                if phones:
                    visual_data['phone'] = phones[0]
            
            return visual_data
            
        except Exception as e:
            print(f"Visual response parsing error: {e}")
            return {}

    async def _merge_extraction_results(self, results: List, original_text: str) -> Dict[str, Any]:
        """Merge results from different extraction methods"""
        merged = {
            'name': '',
            'email': '',
            'phone': '',
            'location': '',
            'title': '',
            'summary': '',
            'experience_years': 0,
            'skills': [],
            'programming_languages': [],
            'frameworks': [],
            'education': [],
            'experience': [],
            'certifications': [],
            'languages': [],
            'linkedin': '',
            'github': '',
            'website': ''
        }
        
        # Alias for backward compatibility with tests
        self._CVProcessor__merge_extraction_results = self._merge_extraction_results
        
        # Priority order: Mistral -> Visual -> spaCy
        mistral_result = results[0] if len(results) > 0 and not isinstance(results[0], Exception) else {}
        visual_result = results[1] if len(results) > 1 and not isinstance(results[1], Exception) else {}
        spacy_result = results[2] if len(results) > 2 and not isinstance(results[2], Exception) else {}
        
        # Merge with priority to Mistral (most structured)
        if isinstance(mistral_result, dict):
            for key, value in mistral_result.items():
                if value and key in merged:
                    merged[key] = value
        
        # Fill missing data from visual analysis
        if isinstance(visual_result, dict):
            for key, value in visual_result.items():
                if not merged.get(key) and value and key in merged:
                    merged[key] = value
        
        # Fill missing data from spaCy
        if isinstance(spacy_result, dict):
            # Name from persons
            if not merged['name'] and spacy_result.get('persons'):
                merged['name'] = spacy_result['persons'][0]
            
            # Email
            if not merged['email'] and spacy_result.get('emails'):
                merged['email'] = spacy_result['emails'][0]
            
            # Phone
            if not merged['phone'] and spacy_result.get('phones'):
                merged['phone'] = spacy_result['phones'][0]
            
            # Skills
            if not merged['skills'] and spacy_result.get('skills'):
                merged['skills'] = spacy_result['skills']
            
            # URLs
            urls = spacy_result.get('urls', [])
            for url in urls:
                if 'linkedin' in url.lower() and not merged['linkedin']:
                    merged['linkedin'] = url
                elif 'github' in url.lower() and not merged['github']:
                    merged['github'] = url
                elif not merged['website'] and url not in [merged['linkedin'], merged['github']]:
                    merged['website'] = url
        
        # Post-processing and validation
        merged = self._validate_and_clean_data(merged, original_text)
        
        return merged

    def _validate_and_clean_data(self, data: Dict[str, Any], original_text: str) -> Dict[str, Any]:
        """Validate and clean extracted data"""
        # Clean name
        if data['name']:
            data['name'] = re.sub(r'[^\w\s\-\.]', '', data['name']).strip()
        
        # Validate email
        if data['email'] and not re.match(r'^[^@]+@[^@]+\.[^@]+$', data['email']):
            data['email'] = ''
        
        # Clean phone
        if data['phone']:
            data['phone'] = re.sub(r'[^\d\+\-\(\)\s]', '', data['phone']).strip()
        
        # Ensure experience_years is a number
        try:
            data['experience_years'] = int(data['experience_years']) if data['experience_years'] else 0
        except (ValueError, TypeError):
            data['experience_years'] = 0
        
        # Clean and deduplicate skills
        if isinstance(data['skills'], list):
            data['skills'] = list(set([skill.strip() for skill in data['skills'] if skill and skill.strip()]))
        
        # Ensure lists are lists
        for list_field in ['programming_languages', 'frameworks', 'certifications', 'languages']:
            if not isinstance(data[list_field], list):
                data[list_field] = []
        
        # Fallback extraction if critical fields are missing
        if not data['name']:
            data['name'] = self._fallback_name_extraction(original_text)
        
        if not data['email']:
            emails = self._extract_emails(original_text)
            if emails:
                data['email'] = emails[0]
        
        return data

    def _fallback_name_extraction(self, text: str) -> str:
        """Fallback method to extract name from text"""
        lines = text.split('\n')
        for line in lines[:5]:  # Check first 5 lines
            line = line.strip()
            if line and len(line.split()) <= 4:  # Likely a name
                # Remove common CV headers
                if not any(header in line.lower() for header in ['curriculum', 'resume', 'cv', 'vitae']):
                    return line
        return ''

    def _clean_json_response(self, json_text: str) -> str:
        """Clean and fix common JSON formatting issues.
        
        Args:
            json_text: The raw JSON string to clean
            
        Returns:
            str: Cleaned JSON string
        """
        if not json_text or not isinstance(json_text, str):
            return "{}"
            
        try:
            # Remove markdown code blocks if present
            json_text = re.sub(r'```(?:json)?\s*([\s\S]*?)\s*```', r'\1', json_text)
            
            # Remove any non-printable characters except newlines and spaces
            json_text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]', '', json_text)
            
            # Remove leading/trailing whitespace and newlines
            json_text = json_text.strip()
            
            # Fix common JSON issues
            json_text = re.sub(r',\s*([}\]])', r'\1', json_text)  # Remove trailing commas
            json_text = re.sub(r'([{\[,])\s*([}\],])', r'\1\2', json_text)  # Remove empty elements
            
            # Ensure the string is valid JSON
            json.loads(json_text)
            return json_text
            
        except json.JSONDecodeError as e:
            print(f"Warning: Failed to clean JSON response: {e}")
            try:
                # Try to extract JSON from malformed response
                match = re.search(r'({[\s\S]*})', json_text)
                if match:
                    return match.group(1)
            except Exception:
                pass
                
            return "{}"    async def _process_with_mistral(self, text: str) -> Dict[str, Any]:
        """Process CV text with Mistral 7B for structured extraction"""
        try:
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
            
            # Call Ollama API
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.ollama_client.chat(
                    model='mistral',
                    messages=[{'role': 'user', 'content': prompt}]
                )
            )
            
            # Extract and parse the response
            if response and 'message' in response and 'content' in response['message']:
                content = response['message']['content']
                # Clean up the response to ensure it's valid JSON
                json_str = self._clean_json_response(content)
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    print(f"Failed to parse JSON response: {json_str}")
                    return {}
            return {}
            
        except Exception as e:
            print(f"Mistral processing error: {e}")
            return {}
