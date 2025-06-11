#!/bin/bash
# coBoarding Deployment Guide & Setup Instructions

# =============================================================================
# COMPLETE DEPLOYMENT GUIDE FOR COBOARDING MVP
# =============================================================================

echo "🚀 Starting coBoarding deployment setup..."

# Prerequisites check
echo "📋 Checking prerequisites..."

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker first."
    echo "Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose not found. Please install Docker Compose first."
    echo "Visit: https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✅ Prerequisites check passed!"

# =============================================================================
# PROJECT STRUCTURE SETUP
# =============================================================================

echo "📁 Creating project structure..."

# Create main project directory
mkdir -p coboarding
cd coboarding

# Create directory structure
mkdir -p {app,worker,cleanup,scripts,uploads,downloads,templates,data}
mkdir -p app/{core,database,utils}
mkdir -p worker/{core,utils}
mkdir -p cleanup/{scripts}

echo "✅ Project structure created!"

# =============================================================================
# DOCKER CONFIGURATION FILES
# =============================================================================

echo "🐳 Creating Docker configuration files..."

# Main app Dockerfile
cat > app/Dockerfile << 'EOF'
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    tesseract-ocr \
    libtesseract-dev \
    poppler-utils \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy model
RUN python -m spacy download en_core_web_sm

# Copy application code
COPY . .

# Expose ports
EXPOSE 8501 8000

# Start command
CMD ["bash", "-c", "streamlit run main.py --server.port=8501 --server.address=0.0.0.0 & uvicorn api:app --host 0.0.0.0 --port 8000 & wait"]
EOF

# Worker Dockerfile
cat > worker/Dockerfile << 'EOF'
FROM python:3.11-slim

# Install system dependencies including Chrome
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    wget \
    gnupg \
    unzip \
    curl \
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Install ChromeDriver
RUN wget -O /tmp/chromedriver.zip https://chromedriver.storage.googleapis.com/114.0.5735.90/chromedriver_linux64.zip \
    && unzip /tmp/chromedriver.zip -d /opt/ \
    && rm /tmp/chromedriver.zip \
    && chmod +x /opt/chromedriver \
    && ln -fs /opt/chromedriver /usr/local/bin/chromedriver

WORKDIR /worker

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium

# Copy worker code
COPY . .

CMD ["python", "worker.py"]
EOF

# Cleanup Dockerfile
cat > cleanup/Dockerfile << 'EOF'
FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    cron \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /cleanup

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Setup cron job for daily cleanup
RUN echo "0 2 * * * /usr/local/bin/python /cleanup/daily_cleanup.py" | crontab -

CMD ["cron", "-f"]
EOF

echo "✅ Docker files created!"

# =============================================================================
# PYTHON REQUIREMENTS FILES
# =============================================================================

echo "📦 Creating requirements files..."

# Main app requirements
cat > app/requirements.txt << 'EOF'
streamlit>=1.28.0
fastapi>=0.104.0
uvicorn>=0.24.0
asyncio
aioredis>=2.0.0
psycopg2-binary>=2.9.0
sqlalchemy>=2.0.0
alembic>=1.12.0
pydantic>=2.4.0
python-multipart>=0.0.6

# AI and ML
ollama>=0.1.7
spacy>=3.7.0
transformers>=4.35.0
torch>=2.1.0
numpy>=1.24.0
pandas>=2.1.0

# Document processing
PyPDF2>=3.0.0
python-docx>=0.8.11
pytesseract>=0.3.10
Pillow>=10.0.0
pdf2image>=1.16.3

# Web automation
playwright>=1.40.0
selenium>=4.15.0
botright>=0.4.0
undetected-chromedriver>=3.5.4

# Computer vision
opencv-python>=4.8.0
easyocr>=1.7.0

# Notifications
requests>=2.31.0
python-telegram-bot>=20.7.0

# Utilities
python-dotenv>=1.0.0
loguru>=0.7.2
tenacity>=8.2.3
httpx>=0.25.0
jinja2>=3.1.2
cryptography>=41.0.7
EOF

# Worker requirements
cat > worker/requirements.txt << 'EOF'
asyncio
aioredis>=2.0.0
psycopg2-binary>=2.9.0
sqlalchemy>=2.0.0
playwright>=1.40.0
selenium>=4.15.0
botright>=0.4.0
ollama>=0.1.7
requests>=2.31.0
python-dotenv>=1.0.0
loguru>=0.7.2
opencv-python>=4.8.0
Pillow>=10.0.0
numpy>=1.24.0
tenacity>=8.2.3
EOF

# Cleanup requirements
cat > cleanup/requirements.txt << 'EOF'
aioredis>=2.0.0
psycopg2-binary>=2.9.0
sqlalchemy>=2.0.0
python-dotenv>=1.0.0
loguru>=0.7.2
asyncio
schedule>=1.2.0
EOF

echo "✅ Requirements files created!"

# =============================================================================
# DATABASE INITIALIZATION SCRIPT
# =============================================================================

echo "🗄️  Creating database initialization script..."

cat > scripts/init.sql << 'EOF'
-- Create coBoarding database schema

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Candidates table
CREATE TABLE IF NOT EXISTS candidates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    email VARCHAR(255),
    phone VARCHAR(50),
    location VARCHAR(255),
    title VARCHAR(255),
    summary TEXT,
    experience_years INTEGER DEFAULT 0,
    skills JSONB DEFAULT '[]',
    cv_data JSONB,
    file_path VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP + INTERVAL '24 hours')
);

-- Job listings table
CREATE TABLE IF NOT EXISTS job_listings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_name VARCHAR(255) NOT NULL,
    position VARCHAR(255) NOT NULL,
    location VARCHAR(255),
    remote BOOLEAN DEFAULT false,
    requirements JSONB DEFAULT '[]',
    salary_range VARCHAR(100),
    urgent BOOLEAN DEFAULT false,
    notification_config JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    active BOOLEAN DEFAULT true
);

-- Applications table
CREATE TABLE IF NOT EXISTS applications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    candidate_id UUID REFERENCES candidates(id) ON DELETE CASCADE,
    job_listing_id UUID REFERENCES job_listings(id) ON DELETE CASCADE,
    match_score DECIMAL(3,2) DEFAULT 0.00,
    status VARCHAR(50) DEFAULT 'pending',
    conversation_data JSONB DEFAULT '{}',
    technical_questions JSONB DEFAULT '[]',
    technical_answers JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    response_deadline TIMESTAMP DEFAULT (CURRENT_TIMESTAMP + INTERVAL '24 hours')
);

-- Notifications table
CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    application_id UUID REFERENCES applications(id) ON DELETE CASCADE,
    notification_type VARCHAR(50) NOT NULL,
    channel VARCHAR(50) NOT NULL,
    recipient VARCHAR(255) NOT NULL,
    message_data JSONB,
    sent_at TIMESTAMP,
    delivery_status VARCHAR(50) DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Audit logs table (for GDPR compliance)
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(255),
    action VARCHAR(100) NOT NULL,
    table_name VARCHAR(100),
    record_id UUID,
    old_data JSONB,
    new_data JSONB,
    user_info JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    retention_until TIMESTAMP DEFAULT (CURRENT_TIMESTAMP + INTERVAL '30 days')
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_candidates_session_id ON candidates(session_id);
CREATE INDEX IF NOT EXISTS idx_candidates_expires_at ON candidates(expires_at);
CREATE INDEX IF NOT EXISTS idx_candidates_email ON candidates(email);

CREATE INDEX IF NOT EXISTS idx_job_listings_active ON job_listings(active);
CREATE INDEX IF NOT EXISTS idx_job_listings_urgent ON job_listings(urgent);

CREATE INDEX IF NOT EXISTS idx_applications_candidate_id ON applications(candidate_id);
CREATE INDEX IF NOT EXISTS idx_applications_job_listing_id ON applications(job_listing_id);
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);
CREATE INDEX IF NOT EXISTS idx_applications_response_deadline ON applications(response_deadline);

CREATE INDEX IF NOT EXISTS idx_notifications_application_id ON notifications(application_id);
CREATE INDEX IF NOT EXISTS idx_notifications_delivery_status ON notifications(delivery_status);

CREATE INDEX IF NOT EXISTS idx_audit_logs_session_id ON audit_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_retention_until ON audit_logs(retention_until);

-- Insert sample job listings
INSERT INTO job_listings (company_name, position, location, remote, requirements, salary_range, urgent, notification_config) VALUES
('TechStart Berlin', 'Senior Python Developer', 'Berlin, Germany', true, '["Python", "Django", "PostgreSQL", "Docker", "AWS"]', '€60,000 - €80,000', true, '{"slack_webhook": "", "email": "hr@techstart.berlin", "teams_webhook": ""}'),
('AI Solutions Warsaw', 'ML Engineer', 'Warsaw, Poland', true, '["Python", "TensorFlow", "PyTorch", "MLOps", "Docker"]', '€50,000 - €70,000', true, '{"email": "careers@aisolutions.pl"}'),
('FinTech Amsterdam', 'Full Stack Developer', 'Amsterdam, Netherlands', false, '["React", "Node.js", "TypeScript", "AWS", "MongoDB"]', '€65,000 - €85,000', false, '{"email": "jobs@fintech.amsterdam"}'),
('Startup Krakow', 'Frontend Developer', 'Krakow, Poland', true, '["React", "TypeScript", "Next.js", "Tailwind CSS"]', '€40,000 - €55,000', true, '{"email": "team@startup.krakow"}'),
('DevOps Company Munich', 'DevOps Engineer', 'Munich, Germany', true, '["Docker", "Kubernetes", "AWS", "Terraform", "Linux"]', '€70,000 - €90,000', false, '{"email": "hr@devops.munich"}'
);

-- Function to automatically delete expired records
CREATE OR REPLACE FUNCTION delete_expired_candidates()
RETURNS void AS $
BEGIN
    DELETE FROM candidates WHERE expires_at < CURRENT_TIMESTAMP;
    DELETE FROM audit_logs WHERE retention_until < CURRENT_TIMESTAMP;
END;
$ LANGUAGE plpgsql;

-- Create n8n schema
CREATE SCHEMA IF NOT EXISTS n8n;
EOF

echo "✅ Database initialization script created!"

# =============================================================================
# SAMPLE JOB LISTINGS JSON
# =============================================================================

echo "📋 Creating sample job listings..."

cat > data/job_listings.json << 'EOF'
[
  {
    "id": "1",
    "company": "TechStart Berlin",
    "position": "Senior Python Developer",
    "location": "Berlin, Germany",
    "remote": true,
    "requirements": ["Python", "Django", "PostgreSQL", "Docker", "AWS"],
    "salary": "€60,000 - €80,000",
    "urgent": true,
    "description": "Join our fast-growing startup building the next generation of AI-powered applications. We need a senior Python developer who can work independently and mentor junior developers.",
    "benefits": ["Remote work", "Equity package", "Learning budget", "Flexible hours"],
    "notification_config": {
      "slack_webhook": "",
      "email": "hr@techstart.berlin",
      "teams_webhook": "",
      "whatsapp_number": ""
    }
  },
  {
    "id": "2",
    "company": "AI Solutions Warsaw",
    "position": "ML Engineer",
    "location": "Warsaw, Poland",
    "remote": true,
    "requirements": ["Python", "TensorFlow", "PyTorch", "MLOps", "Docker"],
    "salary": "€50,000 - €70,000",
    "urgent": true,
    "description": "Build and deploy machine learning models at scale. Work with cutting-edge AI technologies and contribute to products used by millions.",
    "benefits": ["Remote work", "Conference budget", "Latest hardware", "Stock options"],
    "notification_config": {
      "email": "careers@aisolutions.pl"
    }
  },
  {
    "id": "3",
    "company": "FinTech Amsterdam",
    "position": "Full Stack Developer",
    "location": "Amsterdam, Netherlands",
    "remote": false,
    "requirements": ["React", "Node.js", "TypeScript", "AWS", "MongoDB"],
    "salary": "€65,000 - €85,000",
    "urgent": false,
    "description": "Join our mission to revolutionize financial services. Build scalable applications that handle millions of transactions daily.",
    "benefits": ["Relocation assistance", "Health insurance", "Pension plan", "Bike allowance"],
    "notification_config": {
      "email": "jobs@fintech.amsterdam"
    }
  },
  {
    "id": "4",
    "company": "Startup Krakow",
    "position": "Frontend Developer",
    "location": "Krakow, Poland",
    "remote": true,
    "requirements": ["React", "TypeScript", "Next.js", "Tailwind CSS"],
    "salary": "€40,000 - €55,000",
    "urgent": true,
    "description": "Create beautiful and performant user interfaces for our SaaS platform. Work directly with designers and product managers.",
    "benefits": ["Flexible hours", "Home office setup", "Unlimited vacation", "Team events"],
    "notification_config": {
      "email": "team@startup.krakow"
    }
  },
  {
    "id": "5",
    "company": "DevOps Company Munich",
    "position": "DevOps Engineer",
    "location": "Munich, Germany",
    "remote": true,
    "requirements": ["Docker", "Kubernetes", "AWS", "Terraform", "Linux"],
    "salary": "€70,000 - €90,000",
    "urgent": false,
    "description": "Build and maintain infrastructure for high-traffic applications. Implement CI/CD pipelines and ensure 99.9% uptime.",
    "benefits": ["Remote work", "Company car", "Health insurance", "Training budget"],
    "notification_config": {
      "email": "hr@devops.munich"
    }
  }
]
EOF

echo "✅ Sample job listings created!"

# =============================================================================
# ENVIRONMENT CONFIGURATION
# =============================================================================

echo "⚙️  Creating environment configuration..."

cat > .env << 'EOF'
# Database Configuration
DATABASE_URL=postgresql://coboarding:secure_password_123@postgres:5432/coboarding
POSTGRES_DB=coboarding
POSTGRES_USER=coboarding
POSTGRES_PASSWORD=secure_password_123

# Redis Configuration
REDIS_URL=redis://redis:6379

# Ollama Configuration
OLLAMA_URL=http://ollama:11434

# Email Configuration (configure with your SMTP)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
FROM_EMAIL=noreply@coboarding.com
EMAIL_PASSWORD=your_app_password_here

# WhatsApp Business API (optional)
WHATSAPP_TOKEN=your_whatsapp_token
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id

# Application Configuration
ENVIRONMENT=development
SECRET_KEY=your_secret_key_here_change_in_production
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0

# File Storage
UPLOAD_DIR=/app/uploads
MAX_FILE_SIZE=10485760  # 10MB

# GDPR Compliance
DATA_RETENTION_HOURS=24
CLEANUP_ENABLED=true

# n8n Configuration
N8N_BASIC_AUTH_ACTIVE=true
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=admin123
EOF

echo "✅ Environment configuration created!"

# =============================================================================
# DAILY CLEANUP SCRIPT
# =============================================================================

echo "🧹 Creating GDPR cleanup script..."

cat > cleanup/daily_cleanup.py << 'EOF'
#!/usr/bin/env python3
"""
Daily cleanup script for GDPR compliance
Automatically removes expired candidate data and audit logs
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
import aioredis
import asyncpg
from loguru import logger

# Configure logging
logger.add("/cleanup/logs/cleanup.log", rotation="1 week", retention="4 weeks")

class GDPRCleanupService:
    def __init__(self):
        self.redis_url = os.getenv('REDIS_URL', 'redis://redis:6379')
        self.database_url = os.getenv('DATABASE_URL')

    async def run_cleanup(self):
        """Run complete GDPR cleanup process"""
        logger.info("Starting GDPR cleanup process")

        try:
            # Cleanup Redis data
            redis_cleaned = await self._cleanup_redis()

            # Cleanup PostgreSQL data
            postgres_cleaned = await self._cleanup_postgres()

            # Log summary
            logger.info(f"Cleanup completed: Redis={redis_cleaned}, Postgres={postgres_cleaned}")

        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            sys.exit(1)

    async def _cleanup_redis(self):
        """Cleanup expired Redis data"""
        try:
            redis = aioredis.from_url(self.redis_url)

            # Find all GDPR data keys
            keys = await redis.keys("gdpr_data:*")
            cleaned_count = 0

            for key in keys:
                ttl = await redis.ttl(key)
                if ttl <= 0:  # Expired
                    await redis.delete(key)
                    cleaned_count += 1

            # Cleanup old notifications
            notification_keys = await redis.keys("notification:*")
            for key in notification_keys:
                ttl = await redis.ttl(key)
                if ttl <= 0:
                    await redis.delete(key)
                    cleaned_count += 1

            await redis.close()
            logger.info(f"Redis cleanup: removed {cleaned_count} expired entries")
            return cleaned_count

        except Exception as e:
            logger.error(f"Redis cleanup error: {e}")
            return 0

    async def _cleanup_postgres(self):
        """Cleanup expired PostgreSQL data"""
        try:
            conn = await asyncpg.connect(self.database_url)

            # Delete expired candidates and related data
            result = await conn.execute("""
                DELETE FROM candidates
                WHERE expires_at < CURRENT_TIMESTAMP
            """)
            candidates_deleted = int(result.split()[-1])

            # Delete old audit logs (30 days retention)
            result = await conn.execute("""
                DELETE FROM audit_logs
                WHERE retention_until < CURRENT_TIMESTAMP
            """)
            audit_deleted = int(result.split()[-1])

            # Delete old notifications (7 days retention)
            week_ago = datetime.now() - timedelta(days=7)
            result = await conn.execute("""
                DELETE FROM notifications
                WHERE created_at < $1
            """, week_ago)
            notifications_deleted = int(result.split()[-1])

            await conn.close()

            total_deleted = candidates_deleted + audit_deleted + notifications_deleted
            logger.info(f"Postgres cleanup: candidates={candidates_deleted}, audit={audit_deleted}, notifications={notifications_deleted}")

            return total_deleted

        except Exception as e:
            logger.error(f"Postgres cleanup error: {e}")
            return 0

async def main():
    """Main cleanup function"""
    cleanup_service = GDPRCleanupService()
    await cleanup_service.run_cleanup()

if __name__ == "__main__":
    asyncio.run(main())
EOF

chmod +x cleanup/daily_cleanup.py

echo "✅ GDPR cleanup script created!"

# =============================================================================
# DEPLOYMENT COMMANDS
# =============================================================================

echo "🚀 Creating deployment commands..."

cat > deploy.sh << 'EOF'
#!/bin/bash
# coBoarding deployment script

echo "🚀 Deploying coBoarding platform..."

# Build and start services
echo "📦 Building Docker containers..."
docker-compose build --no-cache

echo "🔄 Starting services..."
docker-compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 30

# Check service health
echo "🔍 Checking service health..."
docker-compose ps

# Initialize database
echo "🗄️  Initializing database..."
docker-compose exec postgres psql -U coboarding -d coboarding -f /docker-entrypoint-initdb.d/init.sql

# Download Ollama models
echo "🤖 Downloading AI models..."
docker-compose exec ollama ollama pull llava:7b
docker-compose exec ollama ollama pull mistral:7b-instruct
docker-compose exec ollama ollama pull nomic-embed-text

echo "✅ Deployment completed!"
echo ""
echo "🌐 Services available at:"
echo "  - Main App: http://localhost:8501"
echo "  - API: http://localhost:8000"
echo "  - n8n: http://localhost:5678 (admin/admin123)"
echo "  - Database: localhost:5432"
echo "  - Redis: localhost:6379"
echo ""
echo "📚 Next steps:"
echo "  1. Configure email settings in .env file"
echo "  2. Set up notification webhooks for companies"
echo "  3. Upload your first CV to test the system"
echo "  4. Check logs: docker-compose logs -f"
EOF

chmod +x deploy.sh

# Stop script
cat > stop.sh << 'EOF'
#!/bin/bash
echo "🛑 Stopping coBoarding services..."
docker-compose down
echo "✅ Services stopped!"
EOF

chmod +x stop.sh

# Logs script
cat > logs.sh << 'EOF'
#!/bin/bash
echo "📋 Showing coBoarding logs..."
docker-compose logs -f --tail=100
EOF

chmod +x logs.sh

echo "✅ Deployment scripts created!"

# =============================================================================
# FINAL SETUP AND INSTRUCTIONS
# =============================================================================

echo ""
echo "🎉 coBoarding setup completed successfully!"
echo ""
echo "📁 Project structure:"
echo "  coboarding/"
echo "  ├── docker-compose.yml      # Main orchestration"
echo "  ├── .env                    # Environment config"
echo "  ├── deploy.sh              # Deployment script"
echo "  ├── stop.sh                # Stop services"
echo "  ├── logs.sh                # View logs"
echo "  ├── app/                   # Main application"
echo "  ├── worker/                # Automation worker"
echo "  ├── cleanup/               # GDPR cleanup"
echo "  ├── data/                  # Job listings"
echo "  └── uploads/               # File storage"
echo ""
echo "🚀 To deploy coBoarding:"
echo "  1. cd coboarding"
echo "  2. ./deploy.sh"
echo ""
echo "⚙️  Configuration:"
echo "  - Edit .env file for email/notifications setup"
echo "  - Modify data/job_listings.json for your companies"
echo "  - Configure webhooks in notification_config"
echo ""
echo "📊 Monitoring:"
echo "  - View logs: ./logs.sh"
echo "  - Stop services: ./stop.sh"
echo "  - Health check: docker-compose ps"
echo ""
echo "🔒 Security & Compliance:"
echo "  - Data auto-deletes after 24h (GDPR)"
echo "  - Daily cleanup runs at 2 AM"
echo "  - All communications logged for audit"
echo ""
echo "💡 Need help? Check the documentation or create an issue on GitHub"
echo "    Platform will be available at http://localhost:8501 after deployment"