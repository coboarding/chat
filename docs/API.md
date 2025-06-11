# docs/API.md - Complete API Documentation

## coBoarding Platform API Documentation

### Base URL
- **Development**: `http://localhost:8000`
- **Production**: `https://api.coboarding.com`

### Authentication
Currently using bearer token authentication for protected endpoints:
```bash
Authorization: Bearer <your_token>
```

### Rate Limits
- **General API**: 10 requests/minute per IP
- **CV Upload**: 5 requests/minute per IP  
- **Chat**: 30 requests/minute per IP

---

## 📄 CV Processing Endpoints

### Upload and Process CV
Upload a CV file for AI processing and data extraction.

**Endpoint**: `POST /api/cv/upload`

**Request**:
```bash
curl -X POST http://localhost:8000/api/cv/upload \
  -F "file=@/path/to/cv.pdf" \
  -H "Content-Type: multipart/form-data"
```

**Response**:
```json
{
  "session_id": "session_abc123def456",
  "cv_data": {
    "name": "John Doe",
    "email": "john.doe@example.com",
    "phone": "+48123456789",
    "location": "Warsaw, Poland",
    "title": "Senior Python Developer",
    "summary": "Experienced software developer with 5+ years...",
    "experience_years": 5,
    "skills": ["Python", "Django", "PostgreSQL", "Docker"],
    "programming_languages": ["Python", "JavaScript", "SQL"],
    "frameworks": ["Django", "React", "FastAPI"],
    "education": [{
      "degree": "Master of Computer Science",
      "institution": "University of Warsaw",
      "year": "2019",
      "field": "Computer Science"
    }],
    "experience": [{
      "position": "Senior Python Developer",
      "company": "Tech Company",
      "duration": "2020 - Present",
      "description": "Led development of microservices..."
    }],
    "certifications": ["AWS Solutions Architect"],
    "languages": ["English", "Polish"],
    "linkedin": "https://linkedin.com/in/johndoe",
    "github": "https://github.com/johndoe",
    "website": "https://johndoe.dev"
  },
  "processing_time": 15.3,
  "success": true,
  "message": "CV processed successfully"
}
```

**Error Response**:
```json
{
  "success": false,
  "error": "Unsupported file type",
  "processing_time": 0.1,
  "message": "Please upload PDF, DOCX, or TXT files only"
}
```

### Get CV Data
Retrieve previously processed CV data by session ID.

**Endpoint**: `GET /api/cv/{session_id}`

**Response**:
```json
{
  "cv_data": { ... },
  "session_id": "session_abc123def456"
}
```

### Update CV Data
Update or correct CV information after processing.

**Endpoint**: `PUT /api/cv/{session_id}`

**Request**:
```json
{
  "name": "John Doe",
  "email": "john.doe@gmail.com",
  "skills": ["Python", "Django", "PostgreSQL", "Docker", "Kubernetes"]
}
```

**Response**:
```json
{
  "message": "CV data updated successfully",
  "session_id": "session_abc123def456"
}
```

---

## 🎯 Job Matching Endpoints

### Match Jobs with CV
Find job opportunities that match the candidate's profile.

**Endpoint**: `POST /api/jobs/match`

**Request**:
```json
{
  "session_id": "session_abc123def456",
  "include_remote": true,
  "location_preference": "Warsaw",
  "min_salary": 80000,
  "max_salary": 120000,
  "seniority_level": "senior"
}
```

**Response**:
```json
{
  "matches": [
    {
      "id": "job_001",
      "company": "TechStart Berlin",
      "position": "Senior Python Developer",
      "location": "Berlin, Germany",
      "remote": true,
      "requirements": ["Python", "Django", "PostgreSQL", "Docker"],
      "salary_range": "€60,000 - €80,000",
      "urgent": true,
      "match_score": 0.92,
      "matching_skills": ["Python", "Django", "PostgreSQL", "Docker"],
      "missing_skills": [],
      "benefits": ["Remote work", "Equity package", "Learning budget"],
      "application_url": "https://techstart.com/apply/senior-python"
    }
  ],
  "total_matches": 1,
  "processing_time": 2.1,
  "match_criteria": {
    "include_remote": true,
    "location_preference": "Warsaw",
    "skills_matched": ["Python", "Django", "PostgreSQL"]
  }
}
```

### Get Job Details
Get detailed information about a specific job listing.

**Endpoint**: `GET /api/jobs/{job_id}`

**Response**:
```json
{
  "id": "job_001",
  "company_name": "TechStart Berlin",
  "position": "Senior Python Developer",
  "job_description": "We are looking for an experienced Python developer...",
  "requirements": ["Python", "Django", "PostgreSQL", "Docker"],
  "nice_to_have": ["Kubernetes", "AWS", "React"],
  "responsibilities": [
    "Design and implement scalable backend services",
    "Mentor junior developers",
    "Collaborate with product team"
  ],
  "benefits": ["Remote work", "Equity package", "Learning budget"],
  "application_process": {
    "steps": ["CV Review", "Technical Interview", "Team Interview"],
    "estimated_timeline": "1-2 weeks"
  },
  "company_info": {
    "size": "50-100 employees",
    "industry": "FinTech",
    "founded": 2018,
    "headquarters": "Berlin, Germany"
  }
}
```

---

## 💬 Chat Communication Endpoints

### Send Chat Message
Send a message to an employer or receive AI-powered responses.

**Endpoint**: `POST /api/chat/message`

**Request**:
```json
{
  "message": "I'm very interested in this position. When would be a good time for an interview?",
  "company_id": "job_001",
  "session_id": "session_abc123def456"
}
```

**Response**:
```json
{
  "response": "Thank you for your interest! Based on your profile, you're an excellent match for this role. Our hiring manager is available for interviews this week. Would Tuesday or Wednesday afternoon work for you?",
  "timestamp": "2024-12-01T14:30:22Z",
  "session_id": "session_abc123def456",
  "company_id": "job_001",
  "response_type": "employer_message"
}
```

### Get Chat History
Retrieve conversation history between candidate and employer.

**Endpoint**: `GET /api/chat/history/{session_id}/{company_id}`

**Response**:
```json
{
  "messages": [
    {
      "id": "msg_001",
      "sender": "candidate",
      "message": "I'm interested in this position",
      "timestamp": "2024-12-01T14:25:15Z"
    },
    {
      "id": "msg_002",
      "sender": "employer",
      "message": "Great! Let's schedule an interview",
      "timestamp": "2024-12-01T14:30:22Z"
    }
  ],
  "session_id": "session_abc123def456",
  "company_id": "job_001",
  "total_messages": 2
}
```

---

## 🧠 Technical Validation Endpoints

### Generate Technical Questions
Create technical questions to validate candidate skills.

**Endpoint**: `POST /api/questions/generate`

**Request**:
```json
{
  "session_id": "session_abc123def456",
  "company_id": "job_001"
}
```

**Response**:
```json
{
  "questions": [
    {
      "question": "Explain the difference between Django's select_related() and prefetch_related() methods. When would you use each?",
      "topic": "Django ORM",
      "difficulty": "medium",
      "expected_answer_length": "2-3 sentences"
    },
    {
      "question": "How would you handle database migrations in a production environment with zero downtime?",
      "topic": "Database Management",
      "difficulty": "hard",
      "expected_answer_length": "3-4 sentences"
    }
  ],
  "session_id": "session_abc123def456",
  "company_id": "job_001",
  "total_questions": 2
}
```

### Submit Technical Answers
Submit answers to technical validation questions.

**Endpoint**: `POST /api/questions/submit`

**Request**:
```json
{
  "session_id": "session_abc123def456",
  "company_id": "job_001",
  "answers": [
    {
      "question_id": "q1",
      "answer": "select_related() performs a SQL join and includes related object data in the same query, reducing database hits. prefetch_related() performs separate queries but reduces the number of database queries for many-to-many or reverse foreign key relationships."
    },
    {
      "question_id": "q2", 
      "answer": "Use blue-green deployments with database migrations that are backward compatible. Run migrations before code deployment, ensure new code works with old schema, then deploy new code."
    }
  ]
}
```

**Response**:
```json
{
  "message": "Technical answers submitted successfully",
  "session_id": "session_abc123def456",
  "company_id": "job_001",
  "submission_time": "2024-12-01T15:45:30Z",
  "next_steps": "Your answers will be reviewed by the technical team within 24 hours"
}
```

---

## 🔔 Notification Endpoints

### Send Notification to Employer
Notify employer about new candidate application.

**Endpoint**: `POST /api/notifications/send`

**Request**:
```json
{
  "session_id": "session_abc123def456",
  "company_id": "job_001",
  "message": "I would like to apply for the Senior Python Developer position",
  "notification_type": "candidate_application"
}
```

**Response**:
```json
{
  "notification_results": {
    "slack": {
      "success": true,
      "message": "Slack notification sent"
    },
    "email": {
      "success": true,
      "message": "Email notification sent"
    },
    "teams": {
      "success": false,
      "error": "Teams webhook not configured"
    }
  },
  "success": true
}
```

### Get Notification Status
Check the delivery status of sent notifications.

**Endpoint**: `GET /api/notifications/status/{notification_id}`

**Response**:
```json
{
  "notification_id": "notif_001",
  "status": "delivered",
  "channels": {
    "email": "delivered",
    "slack": "delivered", 
    "teams": "failed"
  },
  "sent_at": "2024-12-01T14:30:22Z",
  "delivered_at": "2024-12-01T14:30:25Z"
}
```

---

## 🤖 Form Automation Endpoints

### Detect Forms on Page
Analyze a webpage to detect form fields for automation.

**Endpoint**: `POST /api/automation/detect-forms`

**Request**:
```json
{
  "url": "https://company.com/careers/apply",
  "method": "hybrid"
}
```

**Response**:
```json
{
  "fields": [
    {
      "element_id": "first_name",
      "field_type": "name",
      "label": "First Name",
      "required": true,
      "confidence": 0.95
    },
    {
      "element_id": "cv_upload",
      "field_type": "file_upload",
      "label": "Upload CV",
      "required": true,
      "confidence": 0.88
    }
  ],
  "total_fields": 2,
  "url": "https://company.com/careers/apply",
  "detection_method": "hybrid"
}
```

### Fill Forms Automatically
Automatically fill detected forms using CV data.

**Endpoint**: `POST /api/automation/fill-forms`

**Request**:
```json
{
  "session_id": "session_abc123def456",
  "url": "https://company.com/careers/apply"
}
```

**Response**:
```json
{
  "success": true,
  "url": "https://company.com/careers/apply",
  "fields_filled": 8,
  "fields_attempted": 10,
  "errors": [
    "Could not fill salary expectation field - field not found"
  ],
  "screenshots": ["base64_encoded_screenshot_data"],
  "processing_time": 45.2
}
```

---

## 🔐 GDPR Compliance Endpoints

### Delete User Data
Delete all data associated with a session (Right to Erasure).

**Endpoint**: `DELETE /api/gdpr/delete/{session_id}`

**Response**:
```json
{
  "message": "Data deleted successfully",
  "session_id": "session_abc123def456",
  "deleted_at": "2024-12-01T16:00:00Z"
}
```

### Get GDPR Compliance Report
Generate compliance report showing data retention status.

**Endpoint**: `GET /api/gdpr/report`

**Response**:
```json
{
  "active_sessions": 45,
  "audit_entries": 1230,
  "average_ttl_hours": 18.5,
  "compliance_status": "compliant",
  "last_cleanup": "2024-12-01T02:00:00Z",
  "data_retention_policy": "24 hours",
  "audit_retention_policy": "30 days"
}
```

---

## 🏥 Health & Monitoring Endpoints

### Application Health Check
Check overall application health and service status.

**Endpoint**: `GET /health` or `GET /healthz`

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2024-12-01T16:15:30Z",
  "services": {
    "redis": "healthy",
    "ollama": "healthy", 
    "database": "healthy"
  },
  "version": "1.0.0",
  "uptime_seconds": 86400
}
```

### Detailed System Metrics
Get detailed metrics for monitoring and alerting.

**Endpoint**: `GET /api/metrics`

**Response**:
```json
{
  "cv_processing": {
    "total_processed": 1250,
    "average_processing_time": 18.5,
    "success_rate": 0.97
  },
  "job_matching": {
    "total_matches": 3400,
    "average_match_score": 0.73,
    "matches_per_cv": 2.7
  },
  "notifications": {
    "total_sent": 890,
    "delivery_rate": 0.95,
    "average_delivery_time": 3.2
  },
  "automation": {
    "forms_detected": 156,
    "forms_filled": 142,
    "success_rate": 0.91
  }
}
```

---

## 📊 Analytics Endpoints

### Get Platform Statistics
Retrieve usage statistics and analytics data.

**Endpoint**: `GET /api/analytics/stats`

**Query Parameters**:
- `period`: `day`, `week`, `month` (default: `day`)
- `metric`: `all`, `applications`, `matches`, `notifications`

**Response**:
```json
{
  "period": "day",
  "date": "2024-12-01",
  "statistics": {
    "cv_uploads": 45,
    "job_matches": 123,
    "applications_sent": 67,
    "interviews_scheduled": 12,
    "offers_made": 3,
    "hires_completed": 1
  },
  "conversion_rates": {
    "cv_to_application": 0.67,
    "application_to_interview": 0.18,
    "interview_to_offer": 0.25,
    "offer_to_hire": 0.33
  }
}
```

---

## Error Codes

### HTTP Status Codes
- `200` - Success
- `201` - Created successfully
- `400` - Bad request (invalid data)
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Resource not found
- `413` - File too large
- `422` - Unprocessable entity (validation failed)
- `429` - Rate limit exceeded
- `500` - Internal server error
- `503` - Service unavailable

### Custom Error Codes
```json
{
  "error_code": "CV_PROCESSING_FAILED",
  "message": "Could not extract text from CV file",
  "details": {
    "file_type": "application/pdf",
    "file_size": 5242880,
    "possible_causes": [
      "Corrupted PDF file",
      "Password-protected PDF",
      "Scanned document without OCR"
    ]
  }
}
```

---

## SDK Examples

### Python SDK Usage
```python
import requests

class coBoardingAPI:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        
    def upload_cv(self, file_path):
        with open(file_path, 'rb') as f:
            response = requests.post(
                f"{self.base_url}/api/cv/upload",
                files={'file': f}
            )
        return response.json()
    
    def match_jobs(self, session_id, preferences=None):
        data = {'session_id': session_id}
        if preferences:
            data.update(preferences)
            
        response = requests.post(
            f"{self.base_url}/api/jobs/match",
            json=data
        )
        return response.json()

# Usage
api = coBoardingAPI()
result = api.upload_cv('/path/to/cv.pdf')
session_id = result['session_id']

matches = api.match_jobs(session_id, {
    'include_remote': True,
    'location_preference': 'Warsaw'
})
```

### JavaScript SDK Usage
```javascript
class coBoardingAPI {
    constructor(baseUrl = 'http://localhost:8000') {
        this.baseUrl = baseUrl;
    }
    
    async uploadCV(file) {
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await fetch(`${this.baseUrl}/api/cv/upload`, {
            method: 'POST',
            body: formData
        });
        
        return response.json();
    }
    
    async matchJobs(sessionId, preferences = {}) {
        const response = await fetch(`${this.baseUrl}/api/jobs/match`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                session_id: sessionId,
                ...preferences
            })
        });
        
        return response.json();
    }
}

// Usage
const api = new coBoardingAPI();
const result = await api.uploadCV(file);
const matches = await api.matchJobs(result.session_id, {
    include_remote: true,
    location_preference: 'Warsaw'
});
```

---

## Webhooks

### Employer Notification Webhook
When enabled, coBoarding will send POST requests to your webhook URL when candidates apply.

**Webhook URL Configuration**: Set in job listing's `notification_config.webhook_url`

**Webhook Payload**:
```json
{
  "event": "candidate_application",
  "timestamp": "2024-12-01T14:30:22Z",
  "candidate": {
    "session_id": "session_abc123def456",
    "name": "John Doe",
    "email": "john.doe@example.com",
    "title": "Senior Python Developer",
    "experience_years": 5,
    "skills": ["Python", "Django", "PostgreSQL"],
    "match_score": 0.92
  },
  "job": {
    "id": "job_001",
    "company": "TechStart Berlin",
    "position": "Senior Python Developer"
  },
  "application": {
    "message": "I'm very interested in this position",
    "applied_at": "2024-12-01T14:30:22Z"
  }
}
```

### Webhook Security
Webhooks include a signature header for verification:
```
X-coBoarding-Signature: sha256=<hmac_signature>
```

Verify the signature using your webhook secret:
```python
import hmac
import hashlib

def verify_webhook(payload, signature, secret):
    expected = hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
```