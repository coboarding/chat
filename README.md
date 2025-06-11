# 🚀 coBoarding - Speed Hiring Platform

[![Python Version](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)](https://pycqa.github.io/isort/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://github.com/yourusername/coboarding/actions/workflows/tests.yml/badge.svg)](https://github.com/yourusername/coboarding/actions)
[![Coverage](https://img.shields.io/codecov/c/github/yourusername/coboarding/main.svg)](https://codecov.io/gh/yourusername/coboarding)
[![Documentation Status](https://readthedocs.org/projects/coboarding/badge/?version=latest)](https://coboarding.readthedocs.io/en/latest/?badge=latest)

**AI-Powered Job Application Automation for SME Tech Companies in Europe**

coBoarding is a comprehensive "speed hiring" platform that connects tech talent with small and medium-sized companies across Europe through intelligent automation and real-time communication. Upload your CV, get matched with companies, and start working within 24 hours.

## 📋 Table of Contents

- [🚀 Features](#-features)
- [🛠️ Tech Stack](#%EF%B8%8F-tech-stack)
- [🚀 Quick Start](#-quick-start)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Development](#development)
  - [Testing](#testing)
  - [Database Management](#database-management)
- [🐳 Docker Setup](#-docker-setup)
- [🤖 AI/ML Components](#-aiml-components)
- [🔒 Security & Compliance](#-security--compliance)
- [🤝 Contributing](#-contributing)
- [📄 License](#-license)

## 🚀 Features

### For Job Seekers
- **📄 Intelligent CV Processing** - AI extracts and structures your experience using local LLM models (Mistral, LLaVA)
- **🎯 Smart Job Matching** - Get matched with relevant positions based on skills and preferences
- **💬 Real-time Communication** - Chat directly with employers through integrated messaging
- **🤖 Automated Applications** - Forms filled automatically using your CV data
- **⚡ 24-Hour Response SLA** - Employers commit to responding within 24 hours

## 🛠️ CV Processor

The CV Processor is a core component that handles CV/Resume parsing and information extraction using AI models.

### Key Features

- **Multi-format Support**: Parses PDF, DOCX, and plain text CVs
- **AI-Powered Extraction**: Uses Mistral and LLaVA models for accurate information extraction
- **Structured Output**: Returns standardized JSON with candidate information
- **Test Mode**: Built-in testing support with mock responses
- **Python 3.12+**: Optimized for the latest Python version

### Installation

```bash
# Install required dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt
```

### Basic Usage

```python
from app.core.cv_processor import CVProcessor
import asyncio

async def process_cv(file_path):
    # Initialize the processor (test_mode=True for development)
    processor = CVProcessor(test_mode=True)
    
    # Process a CV file
    with open(file_path, 'rb') as f:
        result = await processor.process_cv(f)
    
    return result

# Example usage
if __name__ == "__main__":
    result = asyncio.run(process_cv("path/to/cv.pdf"))
    print(result)
```

### Testing

Run the test suite with:

```bash
# Run all tests
pytest tests/

# Run with coverage report
pytest --cov=app tests/

# Generate HTML coverage report
coverage html
```

## 🐍 Python 3.12 Compatibility

The project is fully compatible with Python 3.12 and takes advantage of its features:

- **Pattern Matching**: Used for cleaner control flow
- **Type Hints**: Comprehensive type annotations for better code clarity
- **Async/Await**: Modern asynchronous programming patterns
- **Performance**: Optimized for Python 3.12's improved performance

### Required Python 3.12+ Features

- Type variable defaults (PEP 695)
- Improved error messages
- Faster exception handling
- Enhanced asyncio performance

### For Employers
- **📢 Instant Notifications** - Multi-channel alerts for new candidates
- **🔍 Technical Validation** - AI-generated questions validate candidate skills
- **📊 Smart Matching** - Candidates ranked by relevance and fit
- **💼 Integration Ready** - Works with existing HR tools
- **🇪🇺 GDPR Compliant** - Built for European privacy regulations

## 🛠️ Tech Stack

### Core Technologies
- **Python**: 3.12+
- **Web Framework**: FastAPI
- **Database**: PostgreSQL (production), SQLite (development)
- **ORM**: SQLAlchemy 2.0
- **Migrations**: Alembic

### AI/ML Components
- **LLM**: Ollama (Mistral, LLaVA)
- **NLP**: spaCy, Transformers
- **CV Processing**: Custom CV processor with multi-model extraction
  - Extracts: Name, contact info, skills, experience, education
  - Supports: PDF, DOCX, plain text
  - Handles: Multiple languages, various CV formats
- **Computer Vision**: OpenCV, Tesseract OCR
- **Text Processing**: Regex patterns, custom text cleaning

### Frontend
- **Web Interface**: Streamlit
- **Dashboard**: React (future)
- **Styling**: Tailwind CSS

### Infrastructure
- **Containerization**: Docker, Docker Compose
- **CI/CD**: GitHub Actions
- **Testing**: pytest, pytest-cov, pytest-asyncio
- **Code Quality**: black, isort, flake8, mypy

### Development Tools
- **Package Management**: pip, setuptools
- **Environment Management**: venv, pyenv
- **Documentation**: MkDocs, mkdocstrings
- **Code Quality**: black, isort, flake8, mypy
- **Testing**: pytest, pytest-cov, pytest-asyncio
- **Linting**: Pre-commit hooks for code quality

## 🚀 Quick Start

### Prerequisites

- **Python 3.12 or higher**
  ```bash
  # On Ubuntu/Debian
  sudo apt update && sudo apt install -y python3.12 python3.12-venv python3-pip
  
  # On macOS (using Homebrew)
  brew install python@3.12
  ```

- **Ollama** (for local LLM processing)
  ```bash
  # Install Ollama
  curl -fsSL https://ollama.com/install.sh | sh
  
  # Start Ollama service
  ollama serve &
  
  # Pull required models
  ollama pull mistral
  ollama pull llava
  ```

- **System Dependencies**
  ```bash
  # Install Tesseract OCR and other system dependencies
  sudo apt update && sudo apt install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    poppler-utils \
    libmagic1 \
    python3-dev \
    build-essential \
    libpq-dev
  ```

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/coboarding.git
   cd coboarding/chat
   ```

2. **Set up Python environment**
   ```bash
   # Create and activate virtual environment
   python3.12 -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   
   # Upgrade pip and install dependencies
   pip install --upgrade pip
   pip install -e .[dev]  # Install package in development mode with dev dependencies
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Initialize the database**
   ```bash
   make db-init
   ```

5. **Start the application**
   ```bash
   make run
   ```
   The application will be available at http://localhost:8501

   For development with auto-reload:
   ```bash
   make dev
   ```

## 🧪 Testing

The project includes comprehensive tests to ensure code quality and reliability.

### Running Tests

```bash
# Run all tests
make test

# Run tests with coverage report
make test-cov

# Run only unit tests
make test-unit

# Run only integration tests
make test-integration

# Run tests in parallel
pytest -n auto
```

### Test Coverage

To generate an HTML coverage report:
```bash
make test-cov
# Open htmlcov/index.html in your browser
```

## 🏗️ Development

### Code Style & Quality

```bash
# Format code with black and isort
make format

# Check code style and quality
make lint

# Run static type checking
make typecheck

# Run all checks (lint, typecheck, test)
make check-all
```

### Database Management

```bash
# Initialize database
make db-init

# Create new migration
make db-migrate

# Apply migrations
make db-upgrade

# Revert migrations
make db-downgrade
```

### Pre-commit Hooks

Pre-commit hooks are configured to automatically format and check your code before each commit:

```bash
# Install pre-commit hooks
pre-commit install

# Run pre-commit on all files
pre-commit run --all-files
```

## 🤖 AI/ML Components

The CV processing pipeline uses multiple models for robust information extraction:

1. **Mistral 7B** - For structured data extraction from text
2. **LLaVA** - For visual understanding of CV layouts (images/PDFs)
3. **spaCy** - For NER and basic text processing

### Model Management

```bash
# List available models
ollama list

# Pull a model
ollama pull mistral
ollama pull llava

# Remove a model
ollama rm mistral
```

## 🔒 Security & Compliance

### Environment Variables

Sensitive configuration should be set via environment variables in the `.env` file:

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/coboarding

# Ollama
OLLAMA_BASE_URL=http://localhost:11434

# Security
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440  # 24 hours

# CORS (comma-separated list of origins)
CORS_ORIGINS=http://localhost:8501,http://localhost:3000
```

### Security Best Practices

1. Never commit sensitive data to version control
2. Use environment variables for configuration
3. Keep dependencies updated
4. Run security scans regularly
5. Follow the principle of least privilege for database access

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Workflow

1. Create a new branch for your feature/bugfix
2. Write tests for your changes
3. Implement your changes
4. Ensure all tests pass
5. Update documentation if needed
6. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Ollama](https://ollama.ai/) for providing easy-to-use local LLMs
- [FastAPI](https://fastapi.tiangolo.com/) for the awesome async web framework
- [Streamlit](https://streamlit.io/) for the interactive web interface
- All the amazing open-source libraries that made this project possible

## 🐳 Docker Setup

1. **Build and start services**
   ```bash
   docker-compose up -d --build
   ```

2. **View logs**
   ```bash
   docker-compose logs -f
   ```

3. **Run tests in Docker**
   ```bash
   docker-compose exec web pytest
   ```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -am 'Add some feature'`
4. Push to the branch: `git push origin feature/your-feature`
5. Open a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📧 Contact

For questions or feedback, please open an issue or contact [your-email@example.com](mailto:your-email@example.com)
