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
        echo "⚠️ Warning: Python $PYTHON_VERSION detected. This project works best with Python 3.11 or 3.12."
        echo "Current Python version may cause compatibility issues with some dependencies."
        read -p "Do you want to continue with the current Python version? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Please install Python 3.11 or 3.12 and try again."
            exit 1
        fi
    elif [ $PYTHON_MAJOR -eq 3 ] && [ $PYTHON_MINOR -gt 12 ]; then
        echo "⚠️ Warning: Python $PYTHON_VERSION detected. This project is optimized for Python 3.11 or 3.12."
        echo "Python 3.13+ may have compatibility issues with some dependencies."
        read -p "Do you want to continue with Python $PYTHON_VERSION? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Please install Python 3.11 or 3.12 and try again."
            exit 1
        fi
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

# Install dependencies with version constraints
echo "📚 Installing dependencies..."
if [ $PYTHON_MAJOR -eq 3 ] && [ $PYTHON_MINOR -ge 13 ]; then
    echo "Using compatibility mode for Python 3.13+"
    # Create a temporary requirements file with compatible versions
    grep -v "numpy" requirements.txt > requirements_temp.txt
    echo "numpy<2.0.0" >> requirements_temp.txt
    pip install -r requirements_temp.txt || {
        echo "❌ Dependency installation failed. Some packages may not be compatible with Python $PYTHON_VERSION."
        echo "Consider using Python 3.11 or 3.12 for best compatibility."
        rm requirements_temp.txt
        exit 1
    }
    rm requirements_temp.txt
else
    pip install -r requirements.txt || {
        echo "❌ Dependency installation failed."
        exit 1
    }
fi

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