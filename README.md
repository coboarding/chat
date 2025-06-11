# 🚀 coBoarding - Speed Hiring Platform

**AI-Powered Job Application Automation for SME Tech Companies in Europe**

coBoarding is a comprehensive "speed hiring" platform that connects tech talent with small and medium-sized companies across Europe through intelligent automation and real-time communication. Upload your CV, get matched with companies, and start working within 24 hours.

![coBoarding Logo](https://via.placeholder.com/600x200/2563eb/ffffff?text=coBoarding+-+Speed+Hiring+Platform)

## 🎯 **Key Features**

### For Job Seekers
- **📄 Intelligent CV Processing** - AI extracts and structures your experience using local LLM models
- **🎯 Smart Job Matching** - Get matched with relevant positions based on skills and preferences
- **💬 Real-time Communication** - Chat directly with employers through integrated messaging
- **🤖 Automated Applications** - Forms filled automatically using your CV data
- **⚡ 24-Hour Response SLA** - Employers commit to responding within 24 hours

### For Employers
- **📢 Instant Notifications** - Multi-channel alerts (Slack, Teams, WhatsApp, Email) for new candidates
- **🔍 Technical Validation** - AI-generated questions prevent spam and validate skills
- **📊 Smart Matching** - Get candidates ranked by relevance and fit
- **💼 Integration Ready** - Works with existing HR tools and workflows
- **🇪🇺 GDPR Compliant** - Built for European privacy regulations

## 🏗️ **Architecture Overview**

```mermaid
graph TB
    A[Job Seeker] --> B[CV Upload]
    B --> C[AI Processing]
    C --> D[Job Matching]
    D --> E[Real-time Chat]
    E --> F[Employer Notification]
    F --> G[Technical Validation]
    G --> H[Hiring Decision]
    
    subgraph "AI Stack"
        I[LLaVA 7B - Visual CV Analysis]
        J[Mistral 7B - Data Extraction]
        K[spaCy - NER Processing]
    end
    
    subgraph "Infrastructure"
        L[PostgreSQL - Data Storage]
        M[Redis - GDPR TTL Cache]
        N[Ollama - Local LLM Runtime]
        O[Docker - Containerization]
    end
```

## 🚀 **Quick Start**

### Prerequisites
- **Docker** and **Docker Compose** installed
- **8GB+ RAM** (for local AI models)
- **GPU support** (optional, improves performance)

### 1. Clone and Setup
```bash
git clone https://github.com/your-org/coboarding.git
cd coboarding

# Copy environment template
cp .env.example .env

# Edit configuration
nano .env
```

### 2. Deploy with Docker
```bash
# Deploy complete platform
./deploy.sh

# Monitor logs
./logs.sh

# Stop services
./stop.sh
```

### 3. Access Platform
- **Main App**: http://localhost:8501
- **API Documentation**: http://localhost:8000/docs
- **n8n Workflows**: http://localhost:5678 (admin/admin123)
- **Monitoring**: http://localhost:3000 (with monitoring profile)

## 📁 **Project Structure**

```
coboarding/
├── 🐳 docker-compose.yml          # Service orchestration
├── 📋 README.md                   # This file
├── 🔧 .env                       # Environment configuration
├── 📱 app/                       # Main application
│   ├── 🎯 main.py                # Streamlit interface
│   ├── 🔌 api.py                 # FastAPI backend
│   ├── 🧠 core/                  # Core AI components
│   │   ├── cv_processor.py       # CV analysis & extraction
│   │   ├── form_detector.py      # Form field detection
│   │   ├── automation_engine.py  # Browser automation
│   │   ├── chat_interface.py     # AI-powered chat
│   │   └── notification_service.py # Multi-channel notifications
│   ├── 🗄️ database/             # Database layer
│   │   ├── models.py             # SQLAlchemy models
│   │   └── connection.py         # Connection management
│   └── ⚖️ utils/                # Utilities
│       └── gdpr_compliance.py    # Privacy & compliance
├── 🤖 worker/                    # Background automation
│   ├── worker.py                 # Main worker process
│   └── core/                     # Worker components
├── 🧹 cleanup/                   # GDPR cleanup services
├── 📊 data/                      # Job listings & samples
├── 📤 uploads/                   # CV file storage
└── 📝 templates/                 # Email & chat templates
```

## 🔧 **Configuration**

### Environment Variables
```bash
# Database Configuration
DATABASE_URL=postgresql://user:password@postgres:5432/coboarding
REDIS_URL=redis://redis:6379

# AI Models
OLLAMA_URL=http://ollama:11434

# Email Notifications
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
FROM_EMAIL=noreply@coboarding.com
EMAIL_PASSWORD=your_app_password

# WhatsApp Business (Optional)
WHATSAPP_TOKEN=your_token
WHATSAPP_PHONE_NUMBER_ID=your_id

# GDPR Compliance
DATA_RETENTION_HOURS=24
CLEANUP_ENABLED=true
```

### Company Integration
Edit `data/job_listings.json` to add your companies:

```json
{
  "id": "your-company-1",
  "company": "Your Company Name",
  "position": "Senior Developer",
  "requirements": ["Python", "React", "PostgreSQL"],
  "notification_config": {
    "slack_webhook": "https://hooks.slack.com/...",
    "email": "hr@yourcompany.com",
    "teams_webhook": "https://outlook.office.com/..."
  }
}
```

## 🧠 **AI Models & Performance**

### Local LLM Stack
- **LLaVA 7B** - Visual document understanding and form detection
- **Mistral 7B Instruct** - Structured data extraction and chat responses  
- **spaCy en_core_web_sm** - Named entity recognition and pattern matching
- **nomic-embed-text** - Semantic similarity and matching

### Performance Benchmarks
- **CV Processing**: <30 seconds average
- **Form Detection**: 90%+ accuracy across major job sites
- **Job Matching**: 85%+ relevance with skills-based scoring
- **Response Time**: <2 seconds for chat interactions

### Hardware Requirements
| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **RAM** | 8GB | 16GB+ |
| **CPU** | 4 cores | 8+ cores |
| **Storage** | 50GB | 100GB+ SSD |
| **GPU** | None | NVIDIA with 8GB+ VRAM |

## 📊 **API Reference**

### Core Endpoints

#### CV Processing
```bash
# Upload and process CV
POST /api/cv/upload
Content-Type: multipart/form-data

# Get processed CV data
GET /api/cv/{session_id}

# Update CV information
PUT /api/cv/{session_id}
```

#### Job Matching
```bash
# Match jobs with CV
POST /api/jobs/match
{
  "session_id": "session_abc123",
  "include_remote": true,
  "location_preference": "Berlin"
}
```

#### Communication
```bash
# Send chat message
POST /api/chat/message
{
  "message": "I'm interested in this position",
  "company_id": "company_123",
  "session_id": "session_abc123"
}
```

#### Form Automation
```bash
# Detect forms on page
POST /api/automation/detect-forms
{
  "url": "https://company.com/careers/apply"
}

# Fill forms automatically
POST /api/automation/fill-forms
{
  "session_id": "session_abc123",
  "url": "https://company.com/careers/apply"
}
```

## 🔐 **Security & Compliance**

### GDPR Compliance
- **Data Minimization** - Only collect necessary information
- **Automatic Deletion** - All data expires after 24 hours
- **Right to Erasure** - API endpoint for data deletion
- **Audit Trail** - Complete activity logging
- **Consent Management** - Clear opt-in processes

### EU AI Act Compliance
- **High-Risk System Classification** - HR/recruitment AI
- **Human Oversight** - Required for all hiring decisions
- **Bias Monitoring** - Four-fifths rule implementation
- **Transparency** - Algorithm explanations available
- **Regular Audits** - Automated compliance reporting

### Security Measures
- **Data Encryption** - At rest and in transit
- **API Rate Limiting** - Prevent abuse
- **Input Validation** - Comprehensive sanitization
- **Container Security** - Non-root users, minimal attack surface
- **Network Isolation** - Docker network segmentation

## 📈 **Monitoring & Observability**

### Health Checks
```bash
# Application health
curl http://localhost:8501/healthz

# API health
curl http://localhost:8000/health

# Worker status
docker-compose ps
```

### Metrics & Logging
- **Application Logs** - Structured JSON logging
- **Database Metrics** - Connection pool and query performance
- **Redis Metrics** - Cache hit rates and TTL monitoring
- **Worker Metrics** - Task processing and failure rates

### Optional Monitoring Stack
```bash
# Deploy with monitoring
docker-compose --profile monitoring up -d

# Access Grafana dashboards
open http://localhost:3000
```

## 🌍 **European Market Focus**

### Supported Countries
- **Germany** 🇩🇪 - Primary market, DACH focus
- **Netherlands** 🇳🇱 - International companies hub
- **Poland** 🇵🇱 - Growing tech ecosystem
- **France** 🇫🇷 - Regulatory compliance leader
- **Nordic Countries** 🇸🇪🇩🇰🇳🇴 - Remote-first adoption

### Localization Features
- **Multi-language Support** - English, German, Polish, French
- **Local Job Portals** - Integration with StepStone, Indeed, Pracuj.pl
- **Regional Compliance** - Country-specific privacy laws
- **Currency Support** - EUR, PLN, SEK display
- **Time Zones** - European business hours optimization

## 💰 **Business Model**

### Pricing Tiers

| Plan | Price | Features |
|------|-------|----------|
| **SME** | €50/month | 20 candidates/month, Basic AI matching, Email + Slack |
| **Growth** | €150/month | 100 candidates/month, Advanced AI, Multi-channel notifications |
| **Enterprise** | €500/month + €10K implementation | Unlimited, Custom integrations, White-label |

### Revenue Projections
- **Year 1 Target**: €176,000 ARR (100 SME + 20 Growth + 5 Enterprise)
- **Break-even**: ~200 customers
- **Market Size**: €50-100M addressable by 2030

## 🤝 **Contributing**

### Development Setup
```bash
# Clone repository
git clone https://github.com/your-org/coboarding.git
cd coboarding

# Create development environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r app/requirements.txt
pip install -r worker/requirements.txt

# Run in development mode
export ENVIRONMENT=development
python app/main.py
```

### Code Standards
- **Python 3.11+** required
- **Type hints** for all functions
- **Async/await** for I/O operations
- **Pydantic** for data validation
- **Black** for code formatting
- **pytest** for testing

### CV Tools

Convert your CV from Markdown to PDF using the included script:

```bash
# Using the Makefile (recommended)
make convert-cv INPUT=test/cv.md OUTPUT=test/cv.pdf

# Or directly with Python
python3 scripts/convert_cv.py test/cv.md test/cv.pdf
```

Features:
- Clean, professional PDF output
- Proper formatting of headings, lists, and links
- Custom styling for better readability
- Error handling for missing files

### Makefile Commands

We provide a comprehensive Makefile to simplify common development tasks:

```bash
# Setup and installation
make setup           # Create virtual environment and install dependencies
make install         # Install Python dependencies

# Development
make run             # Run the application
make test            # Run tests
make lint            # Run linters and formatters
make cov             # Run tests with coverage report

# Docker
make docker-build    # Build Docker containers
make docker-up       # Start all services
make docker-down     # Stop all services
make docker-logs     # View container logs

# CV Tools
make convert-cv INPUT=path/to/cv.md OUTPUT=path/to/output.pdf  # Convert CV to PDF
```

### Pull Request Process
1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📞 **Support & Contact**

### Documentation
- **API Docs**: http://localhost:8000/docs
- **Architecture Guide**: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- **Deployment Guide**: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)

### Community
- **GitHub Issues**: Bug reports and feature requests
- **Discussions**: Community support and ideas
- **LinkedIn**: Company updates and networking

### Commercial Support
- **Email**: support@coboarding.com
- **Enterprise**: enterprise@coboarding.com
- **Partnerships**: partners@coboarding.com

## 📝 **License**

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 **Acknowledgments**

- **Ollama Team** - Local LLM runtime
- **Streamlit** - Rapid prototyping framework
- **FastAPI** - Modern Python web framework
- **Playwright** - Reliable browser automation
- **European AI Community** - Compliance guidance and best practices

---

**Built with ❤️ for the European tech community**

*Transform your hiring process from weeks to hours with AI-powered automation and real-time candidate engagement.*

