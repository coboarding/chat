# coBoarding Deployment Guide

This guide covers deployment strategies for coBoarding platform from development to production environments.

## 🚀 Quick Start (Development)

### Prerequisites
- Docker 20.10+ and Docker Compose 2.0+
- 8GB+ RAM (for AI models)
- 50GB+ storage space
- Git

### 1. Clone and Setup
```bash
git clone https://github.com/your-org/coboarding.git
cd coboarding

# Copy environment template
cp .env.example .env

# Edit configuration (see Configuration section below)
nano .env
```

### 2. Deploy
```bash
# Deploy complete platform
./deploy.sh

# Monitor logs
./logs.sh

# Check status
docker-compose ps
```

### 3. Verify Installation
- **Main App**: http://localhost:8501
- **API Docs**: http://localhost:8000/docs
- **n8n Workflows**: http://localhost:5678 (admin/admin123)

---

## 🏗️ Architecture Overview

```mermaid
graph TB
    subgraph "Load Balancer"
        LB[Nginx]
    end
    
    subgraph "Application Layer"
        APP[Streamlit App:8501]
        API[FastAPI:8000]
        WORKER[Form Workers]
    end
    
    subgraph "AI Layer"
        OLLAMA[Ollama LLM:11434]
        MODEL1[LLaVA 7B]
        MODEL2[Mistral 7B]
    end
    
    subgraph "Data Layer"
        PG[PostgreSQL:5432]
        REDIS[Redis:6379]
        UPLOADS[File Storage]
    end
    
    subgraph "Automation"
        N8N[n8n Workflows:5678]
        CLEANUP[GDPR Cleanup]
    end
    
    subgraph "Monitoring"
        PROM[Prometheus:9090]
        GRAF[Grafana:3000]
        ALERT[AlertManager:9093]
    end
    
    LB --> APP
    LB --> API
    API --> PG
    API --> REDIS
    API --> OLLAMA
    WORKER --> PG
    WORKER --> REDIS
    WORKER --> OLLAMA
    OLLAMA --> MODEL1
    OLLAMA --> MODEL2
    N8N --> PG
    CLEANUP --> PG
    CLEANUP --> REDIS
    PROM --> APP
    PROM --> API
    PROM --> PG
    PROM --> REDIS
    GRAF --> PROM
    ALERT --> PROM
```

---

## ⚙️ Configuration

### Environment Variables

#### Core Application
```bash
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
MAX_FILE_SIZE=10485760  # 10MB

# GDPR Compliance
DATA_RETENTION_HOURS=24
CLEANUP_ENABLED=true
```

#### Email Notifications
```bash
# SMTP Configuration
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
FROM_EMAIL=noreply@coboarding.com
EMAIL_PASSWORD=your_app_password_here

# For Gmail: Use App Password, not regular password
# Enable 2FA and generate App Password in Google Account settings
```

#### Messaging Integrations
```bash
# WhatsApp Business API (optional)
WHATSAPP_TOKEN=your_whatsapp_token
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id

# Slack/Teams webhooks (configured per company in job_listings.json)
```

#### n8n Workflow Automation
```bash
N8N_BASIC_AUTH_ACTIVE=true
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=admin123
```

### Company Configuration
Edit `data/job_listings.json` to add your companies:

```json
{
  "id": "your-company-1",
  "company": "Your Company Name",
  "position": "Senior Developer",
  "location": "Berlin, Germany",
  "remote": true,
  "requirements": ["Python", "React", "PostgreSQL"],
  "salary_range": "€60,000 - €80,000",
  "urgent": true,
  "notification_config": {
    "slack_webhook": "https://hooks.slack.com/services/...",
    "email": "hr@yourcompany.com",
    "teams_webhook": "https://outlook.office.com/webhook/...",
    "whatsapp_number": "+491234567890"
  }
}
```

---

## 🐳 Docker Deployment Options

### Option 1: All-in-One (Recommended for Development)
```bash
# Deploy everything on single machine
docker-compose up -d

# With monitoring
docker-compose --profile monitoring up -d

# With production nginx
docker-compose --profile production up -d
```

### Option 2: Microservices (Production)
```bash
# Database only
docker-compose up -d postgres redis

# AI services
docker-compose up -d ollama

# Application services
docker-compose up -d coboarding_app form_worker

# Monitoring (optional)
docker-compose up -d prometheus grafana
```

### Option 3: GPU-Enabled Deployment
For better AI performance with NVIDIA GPUs:

```bash
# Install nvidia-docker2
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update && sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker

# Deploy with GPU support
docker-compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

---

## ☁️ Cloud Deployment

### AWS Deployment

#### Option 1: EC2 + Docker
```bash
# Launch EC2 instance (recommended: t3.large or larger)
# Ubuntu 22.04 LTS, 8GB RAM, 100GB SSD

# Install Docker
sudo apt update
sudo apt install -y docker.io docker-compose
sudo usermod -aG docker ubuntu

# Clone and deploy
git clone https://github.com/your-org/coboarding.git
cd coboarding
./deploy.sh
```

#### Option 2: ECS Fargate
```yaml
# aws/ecs-task-definition.json
{
  "family": "coboarding",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "2048",
  "memory": "8192",
  "containerDefinitions": [
    {
      "name": "coboarding-app",
      "image": "your-registry/coboarding:latest",
      "portMappings": [
        {"containerPort": 8501, "protocol": "tcp"},
        {"containerPort": 8000, "protocol": "tcp"}
      ],
      "environment": [
        {"name": "DATABASE_URL", "value": "postgresql://..."},
        {"name": "REDIS_URL", "value": "redis://..."}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/coboarding",
          "awslogs-region": "eu-central-1"
        }
      }
    }
  ]
}
```

#### Option 3: EKS (Kubernetes)
```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: coboarding
spec:
  replicas: 2
  selector:
    matchLabels:
      app: coboarding
  template:
    metadata:
      labels:
        app: coboarding
    spec:
      containers:
      - name: app
        image: coboarding:latest
        ports:
        - containerPort: 8501
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: coboarding-secrets
              key: database-url
        resources:
          requests:
            memory: "4Gi"
            cpu: "1000m"
          limits:
            memory: "8Gi"
            cpu: "2000m"
```

### Google Cloud Platform

#### Option 1: Compute Engine + Docker
```bash
# Create VM instance
gcloud compute instances create coboarding-vm \
  --machine-type=n1-standard-4 \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=100GB \
  --zone=europe-west3-a

# SSH and deploy
gcloud compute ssh coboarding-vm
git clone https://github.com/your-org/coboarding.git
cd coboarding && ./deploy.sh
```

#### Option 2: Cloud Run
```yaml
# cloudbuild.yaml
steps:
- name: 'gcr.io/cloud-builders/docker'
  args: ['build', '-t', 'gcr.io/PROJECT_ID/coboarding:latest', '.']
- name: 'gcr.io/cloud-builders/docker'
  args: ['push', 'gcr.io/PROJECT_ID/coboarding:latest']
- name: 'gcr.io/cloud-builders/gcloud'
  args: ['run', 'deploy', 'coboarding', '--image', 'gcr.io/PROJECT_ID/coboarding:latest']
``` 