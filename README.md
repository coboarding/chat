# 🚀 coBoarding - Speed Hiring Platform

[![Python Version](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)](https://pycqa.github.io/isort/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**AI-Powered Job Application Automation for SME Tech Companies in Europe**

coBoarding is a comprehensive "speed hiring" platform that connects tech talent with small and medium-sized companies across Europe through intelligent automation and real-time communication. Upload your CV, get matched with companies, and start working within 24 hours.

## 🚀 Features

### For Job Seekers
- **📄 Intelligent CV Processing** - AI extracts and structures your experience using local LLM models
- **🎯 Smart Job Matching** - Get matched with relevant positions based on skills and preferences
- **💬 Real-time Communication** - Chat directly with employers through integrated messaging
- **🤖 Automated Applications** - Forms filled automatically using your CV data
- **⚡ 24-Hour Response SLA** - Employers commit to responding within 24 hours

### For Employers
- **📢 Instant Notifications** - Multi-channel alerts for new candidates
- **🔍 Technical Validation** - AI-generated questions validate candidate skills
- **📊 Smart Matching** - Candidates ranked by relevance and fit
- **💼 Integration Ready** - Works with existing HR tools
- **🇪🇺 GDPR Compliant** - Built for European privacy regulations

## 🛠️ Tech Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic
- **AI/ML**: Ollama (Mistral, LLaVA), spaCy, Transformers
- **Frontend**: Streamlit, React (dashboard)
- **Database**: PostgreSQL, SQLite (development)
- **Infrastructure**: Docker, Docker Compose
- **CI/CD**: GitHub Actions

## 🚀 Quick Start

### Prerequisites

- Python 3.12 or higher
- [Poetry](https://python-poetry.org/) (recommended) or pip
- [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/)
- [Ollama](https://ollama.ai/) (for local LLM processing)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/coboarding.git
   cd coboarding/chat
   ```

2. **Set up Python environment**
   
   Using Poetry (recommended):
   ```bash
   # Install Poetry if you don't have it
   curl -sSL https://install.python-poetry.org | python3 -
   
   # Install dependencies
   poetry install
   poetry shell  # Activate the virtual environment
   ```
   
   Or using venv:
   ```bash
   python3.12 -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Start the application**
   ```bash
   make run  # or 'poetry run streamlit run app/main.py'
   ```
   The application will be available at http://localhost:8501

### Development

- **Run tests**: `make test` or `pytest`
- **Run with auto-reload**: `make dev`
- **Format code**: `make format`
- **Lint code**: `make lint`
- **Type checking**: `make typecheck`

### Database Management

- **Initialize database**: `make db-init`
- **Create migration**: `make db-migrate msg="Your migration message"`
- **Upgrade database**: `make db-upgrade`
- **Downgrade database**: `make db-downgrade`

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
