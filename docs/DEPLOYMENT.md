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
  args: ['build', '-t', 'gcr.io/$PROJECT_ID/coboarding:$COMMIT_SHA', '.']
- name: 'gcr.io/cloud-builders/docker'
  args: ['push', 'gcr.io/$PROJECT_ID/coboarding:$COMMIT_SHA']
- name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
  entrypoint: gcloud
  args:
  - 'run'
  - 'deploy'
  - 'coboarding'
  - '--image'
  - 'gcr.io/$PROJECT_ID/coboarding:$COMMIT_SHA'
  - '--region'
  - 'europe-west1'
  - '--platform'
  - 'managed'
  - '--memory'
  - '8Gi'
  - '--cpu'
  - '4'
  - '--max-instances'
  - '10'
```

### Azure Deployment

#### Azure Container Instances
```bash
# Create resource group
az group create --name coboarding-rg --location westeurope

# Deploy container
az container create \
  --resource-group coboarding-rg \
  --name coboarding \
  --image coboarding:latest \
  --cpu 4 \
  --memory 8 \
  --ports 8501 8000 \
  --environment-variables \
    DATABASE_URL="postgresql://..." \
    REDIS_URL="redis://..." \
  --restart-policy Always
```

---

## 🔧 Production Optimizations

### Performance Tuning

#### PostgreSQL Optimization
```sql
-- postgresql.conf optimizations
shared_buffers = 2GB
effective_cache_size = 6GB
maintenance_work_mem = 512MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 64MB
max_worker_processes = 8
max_parallel_workers_per_gather = 4
max_parallel_workers = 8
max_parallel_maintenance_workers = 4
```

#### Redis Optimization
```conf
# redis.conf optimizations
maxmemory 2gb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
tcp-keepalive 300
timeout 0
tcp-backlog 511
```

#### Nginx Optimization
```nginx
# nginx.conf performance settings
worker_processes auto;
worker_connections 2048;
use epoll;
multi_accept on;
sendfile on;
tcp_nopush on;
tcp_nodelay on;
keepalive_timeout 65;
keepalive_requests 1000;

# Gzip compression
gzip on;
gzip_comp_level 6;
gzip_min_length 1024;
gzip_proxied any;
gzip_vary on;
```

### Security Hardening

#### SSL/TLS Configuration
```bash
# Generate SSL certificates with Let's Encrypt
sudo apt install certbot python3-certbot-nginx

# Obtain certificates
sudo certbot --nginx -d coboarding.com -d www.coboarding.com

# Auto-renewal
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

#### Firewall Setup
```bash
# UFW firewall configuration
sudo ufw enable
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow necessary ports
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS

# Optional: Allow monitoring
sudo ufw allow 3000/tcp  # Grafana
sudo ufw allow 9090/tcp  # Prometheus
```

#### Database Security
```sql
-- Create application-specific user with limited privileges
CREATE USER coboarding_app WITH PASSWORD 'secure_app_password';
GRANT CONNECT ON DATABASE coboarding TO coboarding_app;
GRANT USAGE ON SCHEMA public TO coboarding_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO coboarding_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO coboarding_app;

-- Revoke unnecessary privileges
REVOKE ALL ON SCHEMA public FROM public;
```

### High Availability Setup

#### Database Replication
```yaml
# docker-compose.ha.yml
version: '3.8'
services:
  postgres-primary:
    image: postgres:15-alpine
    environment:
      POSTGRES_REPLICATION_MODE: master
      POSTGRES_REPLICATION_USER: replicator
      POSTGRES_REPLICATION_PASSWORD: repl_password
    volumes:
      - postgres_primary_data:/var/lib/postgresql/data

  postgres-replica:
    image: postgres:15-alpine
    environment:
      POSTGRES_REPLICATION_MODE: slave
      POSTGRES_REPLICATION_USER: replicator
      POSTGRES_REPLICATION_PASSWORD: repl_password
      POSTGRES_MASTER_HOST: postgres-primary
    volumes:
      - postgres_replica_data:/var/lib/postgresql/data
    depends_on:
      - postgres-primary
```

#### Load Balancer Configuration
```nginx
# nginx load balancing
upstream coboarding_backend {
    least_conn;
    server coboarding_app_1:8501 max_fails=3 fail_timeout=30s;
    server coboarding_app_2:8501 max_fails=3 fail_timeout=30s;
    server coboarding_app_3:8501 max_fails=3 fail_timeout=30s;
}

upstream coboarding_api_backend {
    least_conn;
    server coboarding_api_1:8000 max_fails=3 fail_timeout=30s;
    server coboarding_api_2:8000 max_fails=3 fail_timeout=30s;
    server coboarding_api_3:8000 max_fails=3 fail_timeout=30s;
}
```

---

## 📊 Monitoring & Logging

### Prometheus Metrics
Key metrics to monitor:

```yaml
# Custom application metrics
- coboarding_cv_processing_duration_seconds
- coboarding_job_matching_total
- coboarding_notifications_sent_total
- coboarding_form_automation_success_rate
- coboarding_active_sessions_total
- coboarding_data_retention_hours
```

### Grafana Dashboard Setup
```bash
# Import pre-built dashboard
curl -X POST \
  http://admin:admin123@localhost:3000/api/dashboards/db \
  -H 'Content-Type: application/json' \
  -d @monitoring/grafana/dashboards/coboarding-dashboard.json
```

### Log Aggregation
```yaml
# docker-compose.logging.yml
version: '3.8'
services:
  loki:
    image: grafana/loki:latest
    ports:
      - "3100:3100"
    volumes:
      - ./monitoring/loki-config.yml:/etc/loki/local-config.yaml

  promtail:
    image: grafana/promtail:latest
    volumes:
      - ./logs:/var/log/coboarding:ro
      - ./monitoring/promtail-config.yml:/etc/promtail/config.yml
```

### Alerting Rules
```yaml
# monitoring/alert_rules.yml
groups:
  - name: coboarding_critical
    rules:
      - alert: ApplicationDown
        expr: up{job="coboarding-app"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "coBoarding application is down"

      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate detected"

      - alert: GDPRViolation
        expr: coboarding_data_retention_hours > 24
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "GDPR data retention violation"
```

---

## 🔄 CI/CD Pipeline

### GitHub Actions
```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run tests
        run: |
          docker-compose -f docker-compose.test.yml up --abort-on-container-exit
          
  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Build Docker images
        run: |
          docker build -t coboarding:${{ github.sha }} .
          docker tag coboarding:${{ github.sha }} coboarding:latest
          
      - name: Push to registry
        run: |
          echo ${{ secrets.DOCKER_PASSWORD }} | docker login -u ${{ secrets.DOCKER_USERNAME }} --password-stdin
          docker push coboarding:${{ github.sha }}
          docker push coboarding:latest

  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to production
        uses: appleboy/ssh-action@v0.1.5
        with:
          host: ${{ secrets.HOST }}
          username: ${{ secrets.USERNAME }}
          key: ${{ secrets.SSH_KEY }}
          script: |
            cd /opt/coboarding
            docker-compose pull
            docker-compose up -d
            docker system prune -f
```

### GitLab CI/CD
```yaml
# .gitlab-ci.yml
stages:
  - test
  - build
  - deploy

variables:
  DOCKER_IMAGE: $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA

test:
  stage: test
  script:
    - docker-compose -f docker-compose.test.yml up --abort-on-container-exit

build:
  stage: build
  script:
    - docker build -t $DOCKER_IMAGE .
    - docker push $DOCKER_IMAGE
  only:
    - main

deploy_production:
  stage: deploy
  script:
    - ssh $DEPLOY_USER@$DEPLOY_HOST "cd /opt/coboarding && docker-compose pull && docker-compose up -d"
  only:
    - main
  when: manual
```

---

## 🚨 Disaster Recovery

### Backup Strategy
```bash
# Automated daily backups
0 2 * * * /opt/coboarding/scripts/backup.sh

# Weekly full system backup
0 3 * * 0 /opt/coboarding/scripts/backup.sh --full

# Monthly backup to off-site storage
0 4 1 * * /opt/coboarding/scripts/backup.sh --offsite
```

### Recovery Procedures

#### Database Recovery
```bash
# Restore from latest backup
./scripts/restore.sh 20241201_020000 --database

# Point-in-time recovery
pg_restore --clean --if-exists \
  --host=localhost \
  --username=coboarding \
  --dbname=coboarding \
  backup_20241201_020000.dump
```

#### Full System Recovery
```bash
# Complete system restore
./scripts/restore.sh 20241201_020000 --full

# Verify system health
./scripts/health_check.sh
```

---

## 🔍 Troubleshooting

### Common Issues

#### Issue 1: Ollama Models Not Loading
```bash
# Check model status
docker exec coboarding_ollama ollama list

# Pull models manually
docker exec coboarding_ollama ollama pull llava:7b
docker exec coboarding_ollama ollama pull mistral:7b-instruct

# Check GPU availability
docker exec coboarding_ollama nvidia-smi
```

#### Issue 2: High Memory Usage
```bash
# Check container memory usage
docker stats

# Restart services to free memory
docker-compose restart

# Optimize PostgreSQL settings
# Edit postgresql.conf: shared_buffers, work_mem
```

#### Issue 3: Slow CV Processing
```bash
# Check Ollama performance
curl http://localhost:11434/api/tags

# Monitor AI processing queue
docker-compose logs -f coboarding_app | grep "CV processing"

# Scale worker processes
docker-compose up -d --scale form_worker=3
```

#### Issue 4: GDPR Compliance Issues
```bash
# Check data retention
curl http://localhost:8000/api/gdpr/report

# Force cleanup
docker exec coboarding_cleanup python daily_cleanup.py

# Verify deletion
docker exec coboarding_redis redis-cli keys "gdpr_data:*"
```

### Debug Mode
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
docker-compose up -d

# View detailed logs
docker-compose logs -f --tail=100 coboarding_app
```

### Health Checks
```bash
# Application health
curl http://localhost:8501/healthz

# API health  
curl http://localhost:8000/health

# Database health
docker exec coboarding_postgres pg_isready -U coboarding

# Redis health
docker exec coboarding_redis redis-cli ping
```

---

## 📈 Scaling Guidelines

### Vertical Scaling (Single Machine)
- **Minimum**: 4 CPU cores, 8GB RAM, 50GB storage
- **Recommended**: 8 CPU cores, 16GB RAM, 100GB SSD
- **High Load**: 16 CPU cores, 32GB RAM, 500GB NVMe SSD

### Horizontal Scaling (Multiple Machines)

#### Application Tier Scaling
```bash
# Scale application containers
docker-compose up -d --scale coboarding_app=3 --scale form_worker=5
```

#### Database Scaling
```yaml
# Read replicas for scaling reads
version: '3.8'
services:
  postgres-primary:
    image: postgres:15-alpine
    
  postgres-read-replica-1:
    image: postgres:15-alpine
    environment:
      POSTGRES_REPLICATION_MODE: slave
      
  postgres-read-replica-2:
    image: postgres:15-alpine
    environment:
      POSTGRES_REPLICATION_MODE: slave
```

#### Redis Scaling
```yaml
# Redis Cluster for high availability
version: '3.8'
services:
  redis-1:
    image: redis:7-alpine
    command: redis-server --cluster-enabled yes
    
  redis-2:
    image: redis:7-alpine
    command: redis-server --cluster-enabled yes
    
  redis-3:
    image: redis:7-alpine
    command: redis-server --cluster-enabled yes
```

---

## 🌍 Multi-Region Deployment

### AWS Multi-Region Setup
```yaml
# terraform/main.tf
provider "aws" {
  alias  = "primary"
  region = "eu-central-1"
}

provider "aws" {
  alias  = "secondary"
  region = "eu-west-1"
}

# Primary region deployment
module "coboarding_primary" {
  source = "./modules/coboarding"
  providers = {
    aws = aws.primary
  }
  region = "eu-central-1"
}

# Secondary region deployment
module "coboarding_secondary" {
  source = "./modules/coboarding"
  providers = {
    aws = aws.secondary
  }
  region = "eu-west-1"
}
```

### Global Load Balancing
```yaml
# CloudFlare configuration
dns_records:
  - name: "coboarding.com"
    type: "A"
    value: "1.2.3.4"  # Primary region
    ttl: 300
    
  - name: "eu.coboarding.com"
    type: "A"
    value: "5.6.7.8"  # EU region
    ttl: 300
    
load_balancing:
  pools:
    - name: "eu-central"
      origins:
        - address: "1.2.3.4"
          enabled: true
    - name: "eu-west"
      origins:
        - address: "5.6.7.8"
          enabled: true
          
  rules:
    - condition: "ip.geoip.country in {'DE' 'AT' 'CH'}"
      action: "pool"
      value: "eu-central"
    - condition: "ip.geoip.continent eq 'EU'"
      action: "pool"
      value: "eu-west"
```

---

## 📞 Support & Maintenance

### Regular Maintenance Tasks

#### Daily
- [ ] Check application health endpoints
- [ ] Monitor error rates and response times
- [ ] Verify GDPR cleanup execution
- [ ] Review critical alerts

#### Weekly  
- [ ] Update AI models if new versions available
- [ ] Review system performance metrics
- [ ] Check backup integrity
- [ ] Update job listings data

#### Monthly
- [ ] Security updates for all containers
- [ ] Review and optimize database performance
- [ ] Capacity planning review
- [ ] Disaster recovery testing

### Emergency Contacts
- **Infrastructure Issues**: ops@coboarding.com
- **Application Bugs**: dev@coboarding.com  
- **Security Issues**: security@coboarding.com
- **Business Critical**: urgent@coboarding.com

### Documentation Links
- **API Documentation**: `/docs/API.md`
- **Architecture Guide**: `/docs/ARCHITECTURE.md`
- **Troubleshooting**: `/docs/TROUBLESHOOTING.md`
- **Security Guide**: `/docs/SECURITY.md`

---

## ✅ Deployment Checklist

### Pre-Deployment
- [ ] Environment variables configured
- [ ] SSL certificates obtained
- [ ] Firewall rules configured
- [ ] Monitoring setup complete
- [ ] Backup strategy implemented
- [ ] Load testing completed

### Deployment
- [ ] Deploy to staging environment first
- [ ] Run integration tests
- [ ] Verify AI models loading correctly
- [ ] Test GDPR compliance features
- [ ] Validate email/notification delivery
- [ ] Check performance metrics

### Post-Deployment
- [ ] Verify all services healthy
- [ ] Test critical user flows
- [ ] Monitor error rates for 24 hours
- [ ] Verify backup execution
- [ ] Update documentation
- [ ] Notify stakeholders of successful deployment

---

This deployment guide provides comprehensive coverage for getting coBoarding running in any environment from development to enterprise production deployments. Choose the appropriate sections based on your deployment needs and infrastructure requirements.