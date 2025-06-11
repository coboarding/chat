# Makefile for coBoarding - Speed Hiring Platform

# Variables
VENV = venv
# Use pyenv-managed Python if available, otherwise fall back to venv
PYTHON = $(shell command -v python 2>/dev/null || echo $(VENV)/bin/python3.12)
PIP = $(VENV)/bin/pip
PYTHON_VERSION = 3.12
PORT ?= 8501

# Default target
.DEFAULT_GOAL := help

# Help target to show available commands
.PHONY: help
help:
	@echo "\n\033[1mcoBoarding - Available Commands:\033[0m"
	@echo "\n\033[1mSetup:\033[0m"
	@echo "  make setup            Create Python $(PYTHON_VERSION) virtual environment and install dependencies"
	@echo "  install               Install Python dependencies"
	@echo "  clean                 Clean up temporary files and caches"
	@echo "\n\033[1mDevelopment:\033[0m"
	@echo "  run                   Run the application (PORT=XXXX to change port)"
	@echo "  dev                   Run with auto-reload for development"
	@echo "  test                  Run tests"
	@echo "  test-cov              Run tests with coverage report"
	@echo "  lint                  Run linting and code formatting"
	@echo "  format                Format code with black and isort"
	@echo "  typecheck             Run static type checking"
	@echo "\n\033[1mDatabase:\033[0m"
	@echo "  db-init               Initialize database"
	@echo "  db-migrate            Create new migration"
	@echo "  db-upgrade            Upgrade database"
	@echo "  db-downgrade          Downgrade database"

# Setup virtual environment and install dependencies
.PHONY: setup
setup:
	@echo "\n\033[1m🚀 Setting up development environment with Python $(PYTHON_VERSION)...\033[0m"
	python$(PYTHON_VERSION) -m venv $(VENV) || (echo "Python $(PYTHON_VERSION) not found. Please install it first." && exit 1)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@if [ -f requirements-dev.txt ]; then $(PIP) install -r requirements-dev.txt; fi
	@echo "\n\033[1m✅ Setup complete! Activate virtual environment with:\033[0m\n\n  source $(VENV)/bin/activate\n"

# Install Python dependencies
.PHONY: install
install:
	$(PIP) install -r requirements.txt
	@if [ -f requirements-dev.txt ]; then $(PIP) install -r requirements-dev.txt; fi

# Run the application
.PHONY: run
run:
	@echo "\n\033[1m🚀 Starting coBoarding on port $(PORT)...\033[0m"
	PYTHONPATH=$(PWD) $(PYTHON) -m streamlit run app/main.py --server.port=$(PORT) --server.address=0.0.0.0

# Run with auto-reload for development
.PHONY: dev
dev:
	@echo "\n\033[1m🚀 Starting coBoarding in development mode...\033[0m"
	PYTHONPATH=$(PWD) watchfiles '$(PYTHON) -m streamlit run app/main.py --server.port=$(PORT) --server.address=0.0.0.0' .

# Test commands
.PHONY: test
test:
	@echo "\n\033[1m🧪 Running tests...\033[0m"
	PYTHONPATH=$(PWD) $(PYTHON) -m pytest tests/ -v

.PHONY: test-cov
test-cov:
	@echo "\n\033[1m📊 Running tests with coverage...\033[0m"
	PYTHONPATH=$(PWD) $(PYTHON) -m pytest --cov=app --cov-report=term-missing --cov-report=html tests/

# Linting and formatting
.PHONY: lint
lint:
	@echo "\n\033[1m🔍 Running linters...\033[0m"
	$(PYTHON) -m flake8 app/ tests/
	$(PYTHON) -m black --check app/ tests/
	$(PYTHON) -m isort --check-only app/ tests/

.PHONY: format
format:
	@echo "\n\033[1m🎨 Formatting code...\033[0m"
	$(PYTHON) -m black app/ tests/
	$(PYTHON) -m isort app/ tests/

# Type checking
.PHONY: typecheck
typecheck:
	@echo "\n\033[1m🔎 Running type checking...\033[0m"
	$(PYTHON) -m mypy app/

# Database commands
.PHONY: db-init
db-init:
	@echo "\n\033[1m🗄️  Initializing database...\033[0m"
	PYTHONPATH=$(PWD) $(PYTHON) -m alembic upgrade head

.PHONY: db-migrate
db-migrate:
	@if [ -z "$(msg)" ]; then \
		echo "Usage: make db-migrate msg='Migration message'"; \
		exit 1; \
	fi
	PYTHONPATH=$(PWD) $(PYTHON) -m alembic revision --autogenerate -m "$(msg)"

.PHONY: db-upgrade
db-upgrade:
	@echo "\n\033[1m⬆️  Upgrading database...\033[0m"
	PYTHONPATH=$(PWD) $(PYTHON) -m alembic upgrade head

.PHONY: db-downgrade
db-downgrade:
	@echo "\n\033[1m⬇️  Downgrading database...\033[0m"
	PYTHONPATH=$(PWD) $(PYTHON) -m alembic downgrade -1

# Clean up
.PHONY: clean
clean:
	@echo "\n\033[1m🧹 Cleaning up...\033[0m"
	find . -type d -name "__pycache__" -exec rm -r {} +
	find . -type d -name ".pytest_cache" -exec rm -r {} +
	rm -rf .coverage htmlcov/ .mypy_cache/ .pytest_cache/
	find . -type f -name "*.py[co]" -delete
	find . -type d -name "*.egg-info" -exec rm -r {} +

# Help target for backward compatibility
.PHONY: all
all: help
