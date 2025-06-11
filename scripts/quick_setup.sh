#!/bin/bash
# scripts/quick_setup.sh
# Quick setup script for new installations

set -euo pipefail

GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}🚀 coBoarding Quick Setup${NC}"
echo "=================================="

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo -e "${RED}❌ This script should not be run as root${NC}"
   exit 1
fi

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Install Docker if not present
install_docker() {
    echo -e "${YELLOW}📦 Installing Docker...${NC}"
    
    # Update package index
    sudo apt-get update
    
    # Install prerequisites
    sudo apt-get install -y \
        ca-certificates \
        curl \
        gnupg \
        lsb-release
    
    # Add Docker's official GPG key
    sudo mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    
    # Set up repository
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    # Install Docker Engine
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    
    # Add user to docker group
    sudo usermod -aG docker $USER
    
    echo -e "${GREEN}✅ Docker installed successfully${NC}"
    echo -e "${YELLOW}⚠️  Please log out and back in to use Docker without sudo${NC}"
}

# Install Docker Compose if not present
install_docker_compose() {
    echo -e "${YELLOW}📦 Installing Docker Compose...${NC}"
    
    # Download latest version
    DOCKER_COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep 'tag_name' | cut -d\" -f4)
    sudo curl -L "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    
    # Make executable
    sudo chmod +x /usr/local/bin/docker-compose
    
    echo -e "${GREEN}✅ Docker Compose installed successfully${NC}"
}

# Check system requirements
check_requirements() {
    echo -e "${BLUE}🔍 Checking system requirements...${NC}"
    
    # Check RAM
    RAM_GB=$(free -g | awk '/^Mem:/{print $2}')
    if [[ $RAM_GB -lt 8 ]]; then
        echo -e "${YELLOW}⚠️  Warning: Recommended RAM is 8GB+, you have ${RAM_GB}GB${NC}"
    else
        echo -e "${GREEN}✅ RAM: ${RAM_GB}GB${NC}"
    fi
    
    # Check disk space
    DISK_GB=$(df -BG . | awk 'NR==2{print $4}' | sed 's/G//')
    if [[ $DISK_GB -lt 50 ]]; then
        echo -e "${YELLOW}⚠️  Warning: Recommended free space is 50GB+, you have ${DISK_GB}GB${NC}"
    else
        echo -e "${GREEN}✅ Free space: ${DISK_GB}GB${NC}"
    fi
    
    # Check CPU cores
    CPU_CORES=$(nproc)
    if [[ $CPU_CORES -lt 4 ]]; then
        echo -e "${YELLOW}⚠️  Warning: Recommended CPU cores is 4+, you have ${CPU_CORES}${NC}"
    else
        echo -e "${GREEN}✅ CPU cores: ${CPU_CORES}${NC}"
    fi
}

# Setup environment file
setup_environment() {
    echo -e "${BLUE}⚙️  Setting up environment...${NC}"
    
    if [[ ! -f .env ]]; then
        if [[ -f .env.example ]]; then
            cp .env.example .env
            echo -e "${GREEN}✅ Created .env from template${NC}"
        else
            # Create basic .env file
            cat > .env << 'EOF'
# Database Configuration
DATABASE_URL=postgresql://coboarding:secure_password_123@postgres:5432/coboarding
POSTGRES_DB=coboarding
POSTGRES_USER=coboarding
POSTGRES_PASSWORD=secure_password_123

# Redis Configuration
REDIS_URL=redis://redis:6379

# AI Models
OLLAMA_URL=http://ollama:11434

# Application Settings
ENVIRONMENT=development
SECRET_KEY=your_secret_key_here_change_in_production
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0

# File Handling
UPLOAD_DIR=/app/uploads
MAX_FILE_SIZE=10485760

# GDPR Compliance
DATA_RETENTION_HOURS=24
CLEANUP_ENABLED=true

# Email Configuration (configure for production)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
FROM_EMAIL=noreply@coboarding.com
EMAIL_PASSWORD=your_app_password_here

# n8n Configuration
N8N_BASIC_AUTH_ACTIVE=true
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=admin123
EOF
            echo -e "${GREEN}✅ Created basic .env file${NC}"
        fi
    else
        echo -e "${GREEN}✅ .env file already exists${NC}"
    fi
}

# Create necessary directories
create_directories() {
    echo -e "${BLUE}📁 Creating directories...${NC}"
    
    mkdir -p uploads downloads logs data templates/email_templates templates/chat_templates
    chmod 755 uploads downloads logs
    
    echo -e "${GREEN}✅ Directories created${NC}"
}

# Main installation function
main() {
    echo -e "${BLUE}Starting coBoarding installation...${NC}"
    
    # Check system requirements
    check_requirements
    
    # Install Docker if needed
    if ! command_exists docker; then
        install_docker
        NEED_RELOGIN=true
    else
        echo -e "${GREEN}✅ Docker already installed${NC}"
    fi
    
    # Install Docker Compose if needed
    if ! command_exists docker-compose; then
        install_docker_compose
    else
        echo -e "${GREEN}✅ Docker Compose already installed${NC}"
    fi
    
    # Setup environment
    setup_environment
    
    # Create directories
    create_directories
    
    # Make scripts executable
    chmod +x deploy.sh stop.sh logs.sh 2>/dev/null || true
    
    echo ""
    echo -e "${GREEN}🎉 coBoarding setup completed!${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Edit .env file with your configuration"
    echo "2. Run: ./deploy.sh"
    echo "3. Visit: http://localhost:8501"
    echo ""
    
    if [[ "${NEED_RELOGIN:-false}" == "true" ]]; then
        echo -e "${YELLOW}⚠️  Please log out and back in to use Docker without sudo${NC}"
    fi
}

# Run main function
main "$@"

###########################################
# cleanup/scripts/maintenance.py
# Automated maintenance tasks
###########################################

#!/usr/bin/env python3
"""
Automated maintenance tasks for coBoarding platform
Handles database optimization, log rotation, and system cleanup
"""

import asyncio
import os
import sys
import logging
import argparse
from datetime import datetime, timedelta
from pathlib import Path

import asyncpg
import aioredis

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/cleanup/logs/maintenance.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MaintenanceTask:
    def __init__(self):
        self.db_url = os.getenv('DATABASE_URL')
        self.redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        
    async def run_database_maintenance(self):
        """Run database maintenance tasks"""
        logger.info("Starting database maintenance...")
        
        try:
            conn = await asyncpg.connect(self.db_url)
            
            # Update table statistics
            await conn.execute("ANALYZE;")
            logger.info("✅ Updated table statistics")
            
            # Vacuum tables
            await conn.execute("VACUUM;")
            logger.info("✅ Vacuumed tables")
            
            # Reindex tables
            await conn.execute("REINDEX DATABASE coboarding;")
            logger.info("✅ Reindexed database")
            
            # Clean up old audit logs
            week_ago = datetime.now() - timedelta(days=7)
            result = await conn.execute(
                "DELETE FROM audit_logs WHERE retention_until < $1", 
                week_ago
            )
            deleted_count = int(result.split()[-1])
            logger.info(f"✅ Cleaned up {deleted_count} old audit logs")
            
            await conn.close()
            
        except Exception as e:
            logger.error(f"❌ Database maintenance failed: {e}")
            return False
        
        return True
    
    async def run_redis_maintenance(self):
        """Run Redis maintenance tasks"""
        logger.info("Starting Redis maintenance...")
        
        try:
            redis = aioredis.from_url(self.redis_url)
            
            # Get memory info before
            info_before = await redis.info('memory')
            memory_before = info_before.get('used_memory_human', 'unknown')
            
            # Run garbage collection
            await redis.execute_command('MEMORY', 'PURGE')
            
            # Get memory info after
            info_after = await redis.info('memory')
            memory_after = info_after.get('used_memory_human', 'unknown')
            
            logger.info(f"✅ Redis memory: {memory_before} -> {memory_after}")
            
            await redis.close()
            
        except Exception as e:
            logger.error(f"❌ Redis maintenance failed: {e}")
            return False
        
        return True
    
    async def rotate_logs(self):
        """Rotate application logs"""
        logger.info("Starting log rotation...")
        
        log_dir = Path('/app/logs')
        if not log_dir.exists():
            logger.info("No logs directory found, skipping")
            return True
        
        try:
            # Archive logs older than 7 days
            week_ago = datetime.now() - timedelta(days=7)
            archived_count = 0
            
            for log_file in log_dir.glob('*.log'):
                if datetime.fromtimestamp(log_file.stat().st_mtime) < week_ago:
                    archive_name = f"{log_file.stem}_{week_ago.strftime('%Y%m%d')}.log.gz"
                    archive_path = log_dir / 'archive' / archive_name
                    
                    # Create archive directory
                    archive_path.parent.mkdir(exist_ok=True)
                    
                    # Compress and move
                    import gzip
                    with open(log_file, 'rb') as f_in:
                        with gzip.open(archive_path, 'wb') as f_out:
                            f_out.writelines(f_in)
                    
                    log_file.unlink()
                    archived_count += 1
            
            logger.info(f"✅ Archived {archived_count} log files")
            
        except Exception as e:
            logger.error(f"❌ Log rotation failed: {e}")
            return False
        
        return True
    
    async def cleanup_temp_files(self):
        """Clean up temporary files"""
        logger.info("Starting temp file cleanup...")
        
        temp_dirs = ['/tmp', '/app/uploads', '/worker/downloads']
        cleaned_count = 0
        
        try:
            for temp_dir in temp_dirs:
                temp_path = Path(temp_dir)
                if not temp_path.exists():
                    continue
                
                # Remove files older than 24 hours
                day_ago = datetime.now() - timedelta(days=1)
                
                for temp_file in temp_path.glob('*'):
                    if temp_file.is_file():
                        file_time = datetime.fromtimestamp(temp_file.stat().st_mtime)
                        if file_time < day_ago:
                            temp_file.unlink()
                            cleaned_count += 1
            
            logger.info(f"✅ Cleaned up {cleaned_count} temporary files")
            
        except Exception as e:
            logger.error(f"❌ Temp file cleanup failed: {e}")
            return False
        
        return True
    
    async def optimize_ollama_models(self):
        """Optimize Ollama AI models"""
        logger.info("Starting Ollama optimization...")
        
        try:
            import requests
            
            # Check Ollama status
            response = requests.get('http://ollama:11434/api/tags', timeout=10)
            if response.status_code != 200:
                logger.warning("Ollama not accessible, skipping optimization")
                return True
            
            models = response.json().get('models', [])
            logger.info(f"Found {len(models)} models")
            
            # Optional: Preload models to optimize memory
            for model in models:
                model_name = model.get('name', '')
                if model_name:
                    # Warm up model
                    requests.post(
                        'http://ollama:11434/api/generate',
                        json={
                            'model': model_name,
                            'prompt': 'Hello',
                            'stream': False
                        },
                        timeout=30
                    )
            
            logger.info("✅ Ollama models optimized")
            
        except Exception as e:
            logger.error(f"❌ Ollama optimization failed: {e}")
            return False
        
        return True
    
    async def generate_health_report(self):
        """Generate system health report"""
        logger.info("Generating health report...")
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'database': 'unknown',
            'redis': 'unknown',
            'ollama': 'unknown',
            'disk_usage': 'unknown',
            'memory_usage': 'unknown'
        }
        
        try:
            # Check database
            try:
                conn = await asyncpg.connect(self.db_url)
                await conn.execute("SELECT 1")
                report['database'] = 'healthy'
                await conn.close()
            except:
                report['database'] = 'unhealthy'
            
            # Check Redis
            try:
                redis = aioredis.from_url(self.redis_url)
                await redis.ping()
                report['redis'] = 'healthy'
                await redis.close()
            except:
                report['redis'] = 'unhealthy'
            
            # Check Ollama
            try:
                import requests
                response = requests.get('http://ollama:11434/api/tags', timeout=5)
                report['ollama'] = 'healthy' if response.status_code == 200 else 'unhealthy'
            except:
                report['ollama'] = 'unhealthy'
            
            # Check disk usage
            try:
                import shutil
                total, used, free = shutil.disk_usage('/')
                usage_percent = (used / total) * 100
                report['disk_usage'] = f"{usage_percent:.1f}%"
            except:
                pass
            
            # Check memory usage
            try:
                with open('/proc/meminfo', 'r') as f:
                    meminfo = f.read()
                    for line in meminfo.split('\n'):
                        if 'MemAvailable:' in line:
                            available_kb = int(line.split()[1])
                            available_gb = available_kb / 1024 / 1024
                            report['memory_usage'] = f"{available_gb:.1f}GB available"
                            break
            except:
                pass
            
            # Save report
            report_path = Path('/cleanup/logs/health_report.json')
            report_path.parent.mkdir(exist_ok=True)
            
            import json
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2)
            
            logger.info(f"✅ Health report saved to {report_path}")
            
        except Exception as e:
            logger.error(f"❌ Health report generation failed: {e}")
            return False
        
        return True

async def main():
    parser = argparse.ArgumentParser(description='coBoarding Maintenance Tasks')
    parser.add_argument('--task', choices=[
        'database', 'redis', 'logs', 'temp', 'ollama', 'health', 'all'
    ], default='all', help='Specific task to run')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done')
    
    args = parser.parse_args()
    
    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be made")
        return
    
    maintenance = MaintenanceTask()
    tasks_run = 0
    tasks_successful = 0
    
    logger.info(f"Starting maintenance tasks: {args.task}")
    
    if args.task in ['database', 'all']:
        tasks_run += 1
        if await maintenance.run_database_maintenance():
            tasks_successful += 1
    
    if args.task in ['redis', 'all']:
        tasks_run += 1
        if await maintenance.run_redis_maintenance():
            tasks_successful += 1
    
    if args.task in ['logs', 'all']:
        tasks_run += 1
        if await maintenance.rotate_logs():
            tasks_successful += 1
    
    if args.task in ['temp', 'all']:
        tasks_run += 1
        if await maintenance.cleanup_temp_files():
            tasks_successful += 1
    
    if args.task in ['ollama', 'all']:
        tasks_run += 1
        if await maintenance.optimize_ollama_models():
            tasks_successful += 1
    
    if args.task in ['health', 'all']:
        tasks_run += 1
        if await maintenance.generate_health_report():
            tasks_successful += 1
    
    logger.info(f"Maintenance completed: {tasks_successful}/{tasks_run} tasks successful")
    
    if tasks_successful == tasks_run:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())

###########################################
# test_config.py
# Test configuration and utilities
###########################################

# test/conftest.py
"""
Pytest configuration and fixtures for coBoarding tests
"""

import pytest
import asyncio
import tempfile
import os
from pathlib import Path

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def test_env():
    """Set up test environment variables"""
    original_env = dict(os.environ)
    
    # Set test environment variables
    os.environ.update({
        'ENVIRONMENT': 'test',
        'DATABASE_URL': 'sqlite:///test.db',
        'REDIS_URL': 'redis://localhost:6379/1',
        'OLLAMA_URL': 'http://localhost:11434',
        'DATA_RETENTION_HOURS': '1',
        'LOG_LEVEL': 'DEBUG'
    })
    
    yield
    
    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)

@pytest.fixture
def temp_upload_dir():
    """Create temporary upload directory"""
    with tempfile.TemporaryDirectory() as temp_dir:
        upload_dir = Path(temp_dir) / 'uploads'
        upload_dir.mkdir()
        yield upload_dir

@pytest.fixture
def sample_cv_data():
    """Sample CV data for testing"""
    return {
        'name': 'Test User',
        'email': 'test@example.com',
        'phone': '+48123456789',
        'location': 'Warsaw, Poland',
        'title': 'Python Developer',
        'summary': 'Experienced Python developer',
        'experience_years': 3,
        'skills': ['Python', 'Django', 'PostgreSQL'],
        'programming_languages': ['Python', 'JavaScript'],
        'frameworks': ['Django', 'React'],
        'education': [{
            'degree': 'Bachelor of Computer Science',
            'institution': 'Test University',
            'year': '2020',
            'field': 'Computer Science'
        }],
        'certifications': ['AWS Certified'],
        'languages': ['English', 'Polish']
    }

@pytest.fixture
def sample_job_listing():
    """Sample job listing for testing"""
    return {
        'id': 'test_job_001',
        'company': 'Test Company',
        'position': 'Python Developer',
        'location': 'Warsaw, Poland',
        'remote': True,
        'requirements': ['Python', 'Django', 'PostgreSQL'],
        'salary_range': '€50,000 - €70,000',
        'urgent': True,
        'notification_config': {
            'email': 'test@company.com'
        }
    }

###########################################
# .env.example
# Environment variables template
###########################################

# Database Configuration
DATABASE_URL=postgresql://coboarding:secure_password_123@postgres:5432/coboarding
POSTGRES_DB=coboarding
POSTGRES_USER=coboarding
POSTGRES_PASSWORD=secure_password_123
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

# Redis Configuration
REDIS_URL=redis://redis:6379

# AI Models Configuration
OLLAMA_URL=http://ollama:11434

# Application Settings
ENVIRONMENT=development
SECRET_KEY=your_secret_key_here_change_in_production
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0
DEBUG=true

# File Handling
UPLOAD_DIR=/app/uploads
MAX_FILE_SIZE=10485760  # 10MB in bytes
ALLOWED_FILE_TYPES=pdf,docx,txt

# GDPR Compliance
DATA_RETENTION_HOURS=24
CLEANUP_ENABLED=true

# Email Configuration
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
FROM_EMAIL=noreply@coboarding.com
EMAIL_PASSWORD=your_app_password_here
EMAIL_USE_TLS=true

# WhatsApp Business API (Optional)
WHATSAPP_TOKEN=your_whatsapp_business_token
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id

# Slack Integration (Optional)
SLACK_BOT_TOKEN=xoxb-your-slack-bot-token
SLACK_SIGNING_SECRET=your_slack_signing_secret

# n8n Workflow Automation
N8N_BASIC_AUTH_ACTIVE=true
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=admin123

# API Configuration
API_TOKEN=dev_token_123_change_in_production
RATE_LIMIT_PER_MINUTE=60

# Worker Configuration
WORKER_CONCURRENCY=3
TASK_TIMEOUT=300
MAX_RETRIES=3
RETRY_DELAY=60

# Browser Automation Settings
HEADLESS=true
BROWSER_TIMEOUT=60
DOWNLOAD_TIMEOUT=30

# Performance Settings
MEMORY_LIMIT_MB=2048
CPU_LIMIT=2.0

# Logging Configuration
LOG_LEVEL=INFO
LOG_RETENTION=7 days

# Monitoring Configuration (Optional)
PROMETHEUS_ENABLED=false
GRAFANA_ADMIN_PASSWORD=admin123

# SSL/Security (Production)
USE_SSL=false
SSL_CERT_PATH=/etc/nginx/ssl/cert.pem
SSL_KEY_PATH=/etc/nginx/ssl/key.pem

# Backup Configuration
BACKUP_ENABLED=true
BACKUP_RETENTION_DAYS=7
BACKUP_SCHEDULE=0 2 * * *

###########################################
# Dockerfile.test
# Specialized Docker image for testing
###########################################

FROM python:3.11-slim

# Install system dependencies for testing
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    tesseract-ocr \
    libtesseract-dev \
    chromium \
    chromium-driver \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python test dependencies
COPY requirements.txt .
COPY test/requirements-test.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r test/requirements-test.txt

# Install spaCy model
RUN python -m spacy download en_core_web_sm

# Copy application code
COPY . .

# Set environment for testing
ENV ENVIRONMENT=test
ENV PYTHONPATH=/app

# Run tests by default
CMD ["pytest", "-v", "--cov=.", "--cov-report=html", "--cov-report=term"]

###########################################
# test/requirements-test.txt
# Testing dependencies
###########################################

pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-cov>=4.1.0
pytest-mock>=3.11.0
pytest-xdist>=3.3.0
pytest-benchmark>=4.0.0
pytest-timeout>=2.1.0

# HTTP testing
httpx>=0.24.0
respx>=0.20.0

# Database testing
pytest-postgresql>=5.0.0
pytest-redis>=3.0.0

# Factory patterns for test data
factory-boy>=3.3.0
faker>=19.0.0

# Load testing
locust>=2.16.0

# API testing
tavern>=2.0.0

# Visual testing (for form automation)
selenium>=4.15.0
pytest-selenium>=4.1.0

# Code quality
black>=23.7.0
flake8>=6.0.0
mypy>=1.5.0
bandit>=1.7.5

# Documentation testing
pytest-doctestplus>=1.0.0

###########################################
# docker-compose.test.yml
# Testing environment setup
###########################################

version: '3.8'

services:
  test-postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: coboarding_test
      POSTGRES_USER: test_user
      POSTGRES_PASSWORD: test_password
    ports:
      - "5433:5432"
    tmpfs:
      - /var/lib/postgresql/data

  test-redis:
    image: redis:7-alpine
    ports:
      - "6380:6379"
    command: redis-server --save ""

  test-ollama:
    image: ollama/ollama:latest
    ports:
      - "11435:11434"
    environment:
      - OLLAMA_HOST=0.0.0.0
    volumes:
      - test_ollama_data:/root/.ollama

  coboarding-test:
    build:
      context: .
      dockerfile: Dockerfile.test
    environment:
      - DATABASE_URL=postgresql://test_user:test_password@test-postgres:5432/coboarding_test
      - REDIS_URL=redis://test-redis:6379
      - OLLAMA_URL=http://test-ollama:11434
      - ENVIRONMENT=test
    volumes:
      - .:/app
      - ./test-reports:/app/test-reports
    depends_on:
      - test-postgres
      - test-redis
      - test-ollama
    command: pytest -v --cov=. --cov-report=html:/app/test-reports/coverage

volumes:
  test_ollama_data:

###########################################
# healthcheck.sh
# System health check script
###########################################

#!/bin/bash
# scripts/healthcheck.sh

set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "🏥 coBoarding Health Check"
echo "========================="

# Function to check service health
check_service() {
    local service_name="$1"
    local health_url="$2"
    local timeout="${3:-10}"
    
    echo -n "Checking $service_name... "
    
    if curl -sf --max-time "$timeout" "$health_url" >/dev/null 2>&1; then
        echo -e "${GREEN}✅ Healthy${NC}"
        return 0
    else
        echo -e "${RED}❌ Unhealthy${NC}"
        return 1
    fi
}

# Function to check docker service
check_docker_service() {
    local service_name="$1"
    local container_name="$2"
    
    echo -n "Checking $service_name container... "
    
    if docker ps --filter "name=$container_name" --filter "status=running" | grep -q "$container_name"; then
        echo -e "${GREEN}✅ Running${NC}"
        return 0
    else
        echo -e "${RED}❌ Not running${NC}"
        return 1
    fi
}

# Initialize counters
total_checks=0
failed_checks=0

# Check Docker services
echo "🐳 Docker Services:"
for service in coboarding_app coboarding_postgres coboarding_redis coboarding_ollama; do
    total_checks=$((total_checks + 1))
    if ! check_docker_service "${service#coboarding_}" "$service"; then
        failed_checks=$((failed_checks + 1))
    fi
done

echo ""

# Check HTTP endpoints
echo "🌐 HTTP Endpoints:"
endpoints=(
    "Main App:http://localhost:8501"
    "API:http://localhost:8000/health"
    "API Docs:http://localhost:8000/docs"
    "Ollama:http://localhost:11434/api/tags"
)

for endpoint in "${endpoints[@]}"; do
    name="${endpoint%%:*}"
    url="${endpoint#*:}"
    total_checks=$((total_checks + 1))
    if ! check_service "$name" "$url"; then
        failed_checks=$((failed_checks + 1))
    fi
done

echo ""

# Check disk space
echo "💾 System Resources:"
echo -n "Disk space... "
disk_usage=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
if [[ $disk_usage -lt 90 ]]; then
    echo -e "${GREEN}✅ ${disk_usage}% used${NC}"
else
    echo -e "${YELLOW}⚠️  ${disk_usage}% used (high)${NC}"
    failed_checks=$((failed_checks + 1))
fi
total_checks=$((total_checks + 1))

# Check memory
echo -n "Memory usage... "
if command -v free >/dev/null 2>&1; then
    memory_usage=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100.0}')
    if [[ $memory_usage -lt 90 ]]; then
        echo -e "${GREEN}✅ ${memory_usage}% used${NC}"
    else
        echo -e "${YELLOW}⚠️  ${memory_usage}% used (high)${NC}"
        failed_checks=$((failed_checks + 1))
    fi
else
    echo -e "${YELLOW}⚠️  Cannot check memory${NC}"
fi
total_checks=$((total_checks + 1))

echo ""

# Summary
echo "📊 Health Check Summary:"
echo "========================"
healthy_checks=$((total_checks - failed_checks))
echo "Total checks: $total_checks"
echo -e "Healthy: ${GREEN}$healthy_checks${NC}"
if [[ $failed_checks -gt 0 ]]; then
    echo -e "Failed: ${RED}$failed_checks${NC}"
    echo ""
    echo -e "${RED}❌ System is not fully healthy${NC}"
    echo "Check the failed services and try restarting them:"
    echo "  docker-compose restart <service_name>"
    exit 1
else
    echo -e "Failed: ${GREEN}0${NC}"
    echo ""
    echo -e "${GREEN}✅ All systems healthy!${NC}"
    exit 0
fi