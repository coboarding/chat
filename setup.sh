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

# Check Python version (ensure compatibility)
echo "🐍 Checking Python version..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)
    
    if [ $PYTHON_MAJOR -lt 3 ] || ([ $PYTHON_MAJOR -eq 3 ] && [ $PYTHON_MINOR -lt 11 ]); then
        echo "❌ Error: Python $PYTHON_VERSION detected. This project requires Python 3.11 or 3.12."
        echo "Please install Python 3.11 or 3.12 and try again."
        exit 1
    elif [ $PYTHON_MAJOR -eq 3 ] && [ $PYTHON_MINOR -gt 12 ]; then
        echo "❌ Error: Python $PYTHON_VERSION detected. This project requires Python 3.11 or 3.12."
        echo "Python 3.13+ has confirmed compatibility issues with key dependencies."
        echo "Please install Python 3.11 or 3.12 and try again."
        
        # Check if pyenv is available to suggest a solution
        if command -v pyenv &> /dev/null; then
            echo "
💡 Tip: You have pyenv installed. You can install and use Python 3.12 with:"
            echo "  pyenv install 3.12.0"
            echo "  pyenv local 3.12.0"
        else
            echo "
💡 Tip: Consider using pyenv to manage Python versions:"
            echo "  https://github.com/pyenv/pyenv#installation"
        fi
        exit 1
    else
        echo "✅ Python $PYTHON_VERSION detected. Compatible version."
    fi
else
    echo "❌ Python 3 not found. Please install Python 3.11 or 3.12."
    exit 1
fi

# Check for Tesseract OCR (required for CV processing)
echo "📄 Checking for Tesseract OCR..."
if ! command -v tesseract &> /dev/null; then
    echo "⚠️ Tesseract OCR not found. This is required for CV processing features."
    read -p "Do you want to install Tesseract OCR now? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if [ -f /etc/debian_version ]; then
            echo "Installing Tesseract OCR via apt..."
            sudo apt-get update && sudo apt-get install -y tesseract-ocr
        elif [ -f /etc/redhat-release ]; then
            echo "Installing Tesseract OCR via dnf..."
            sudo dnf install -y tesseract
        elif command -v brew &> /dev/null; then
            echo "Installing Tesseract OCR via Homebrew..."
            brew install tesseract
        else
            echo "❌ Automatic installation not supported for your OS."
            echo "Please install Tesseract OCR manually: https://github.com/tesseract-ocr/tesseract"
        fi
    fi
fi

# Check for Ansible
echo "🔧 Checking for Ansible..."
if ! command -v ansible &> /dev/null; then
    echo "⚠️ Ansible not found. This is required for infrastructure automation."
    read -p "Do you want to install Ansible now? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Installing Ansible..."
        python3 -m pip install ansible
    fi
fi

# Setup virtual environment
echo "🌐 Setting up Python virtual environment..."
if [ -d "venv" ]; then
    echo "Virtual environment already exists. Updating..."
else
    echo "Creating new virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
echo "📦 Upgrading pip..."
pip install --upgrade pip

# Install dependencies in groups for better reliability
echo "📚 Installing dependencies..."

# Define core dependencies that must be installed
CORE_DEPS="streamlit fastapi uvicorn python-dotenv jinja2"
DB_DEPS="sqlalchemy psycopg2-binary aioredis alembic"
API_DEPS="pydantic python-multipart httpx requests"
AI_DEPS="spacy transformers pandas"
COMPAT_DEPS="numpy==1.24.4 torch==2.1.2"

echo "📦 Installing core web dependencies..."
pip install $CORE_DEPS || {
    echo "❌ Core web dependency installation failed."
    exit 1
}

echo "📦 Installing database dependencies..."
pip install $DB_DEPS || {
    echo "⚠️ Some database dependencies could not be installed. Continuing anyway..."
}

echo "📦 Installing API dependencies..."
pip install $API_DEPS || {
    echo "⚠️ Some API dependencies could not be installed. Continuing anyway..."
}

echo "📦 Installing AI dependencies (may take a while)..."
pip install $COMPAT_DEPS || {
    echo "⚠️ Compatible versions of numpy/torch could not be installed. Trying without version constraints..."
    pip install numpy torch || {
        echo "⚠️ Could not install numpy/torch. Some AI features may not work."
    }
}

pip install $AI_DEPS || {
    echo "⚠️ Some AI dependencies could not be installed. Some features may not work."
}

echo "📦 Installing document processing dependencies..."
pip install PyPDF2 python-docx pytesseract Pillow pdf2image WeasyPrint markdown || {
    echo "⚠️ Some document processing dependencies could not be installed. Document processing features may not work."
}

echo "📦 Installing optional dependencies..."
pip install loguru tenacity cryptography || {
    echo "⚠️ Some optional dependencies could not be installed."
}

echo "✅ Core dependencies installed successfully."
echo "⚠️ Note: Some optional dependencies may not have been installed due to compatibility issues."
echo "    This is normal and the core application should still function."

# Setup Ansible project
echo "🔄 Setting up Ansible project..."
if [ -d "ansible" ]; then
    echo "✅ Ansible directory exists."
    
    # Check if ansible.cfg exists
    if [ ! -f "ansible/ansible.cfg" ]; then
        echo "Creating ansible.cfg..."
        cat > ansible/ansible.cfg << EOF
[defaults]
inventory = ./inventory/hosts
host_key_checking = False
gather_facts = False
become = False
EOF
    fi
    
    # Check if inventory exists
    if [ ! -d "ansible/inventory" ]; then
        echo "Creating inventory directory..."
        mkdir -p ansible/inventory
        
        echo "Creating hosts file..."
        cat > ansible/inventory/hosts << EOF
[webservers]
localhost ansible_connection=local

[dbservers]
localhost ansible_connection=local
EOF
    fi
    
    echo "✅ Ansible configuration ready."
else
    echo "❌ Ansible directory not found. Please run the Ansible setup first."
    echo "You can run: make ansible-check to verify your Ansible configuration."
fi

# Create necessary directories for the project
echo "📁 Creating necessary directories..."
mkdir -p ~/ansible_demo/www
mkdir -p ~/ansible_demo/db

# Check Docker configuration
echo "🐳 Checking Docker configuration..."
if [ ! -f "Dockerfile" ]; then
    echo "⚠️ Dockerfile not found in the root directory."
    read -p "Do you want to create a basic Dockerfile? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Creating Dockerfile..."
        cat > Dockerfile << EOF
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose ports
EXPOSE 8501
EXPOSE 8000

# Command to run the application
CMD ["streamlit", "run", "app/main.py"]
EOF
        echo "✅ Dockerfile created."
    fi
fi

# Check if docker-compose.yml exists
if [ ! -f "docker-compose.yml" ]; then
    echo "⚠️ docker-compose.yml not found."
    read -p "Do you want to create a basic docker-compose.yml? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Creating docker-compose.yml..."
        cat > docker-compose.yml << EOF
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8501:8501"
      - "8000:8000"
    volumes:
      - .:/app
    depends_on:
      - redis
      - postgres
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@postgres:5432/coboarding
      - REDIS_URL=redis://redis:6379/0

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=coboarding
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama

volumes:
  redis_data:
  postgres_data:
  ollama_data:
EOF
        echo "✅ docker-compose.yml created."
    fi
fi

# Run Ansible playbook
echo "🎭 Running Ansible playbook..."
cd ansible && ansible-playbook site.yml || {
    echo "⚠️ Ansible playbook execution failed. Check the error messages above."
}
cd ..

echo "
=============================================================================
🎉 coBoarding setup completed!
=============================================================================

To start the application:
  make run

To run tests:
  make test

To start with Docker:
  make docker-build
  make docker-up

For more commands:
  make help

Documentation:
  - README.md: Main project documentation
  - docs/API.md: API documentation
  - docs/DEPLOYMENT.md: Detailed deployment guide
  - ansible/README.md: Ansible automation documentation

Enjoy using coBoarding!
"