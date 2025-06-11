# Makefile for coBoarding - Speed Hiring Platform

# Variables
VENV = venv
PYTHON = $(VENV)/bin/python3
PIP = $(VENV)/bin/pip

# Default target
.DEFAULT_GOAL := help

# Help target to show available commands
.PHONY: help
help:
	@echo "\n\033[1mcoBoarding - Available Commands:\033[0m"
	@echo "\n\033[1mSetup:\033[0m"
	@echo "  make setup            Create virtual environment and install dependencies"
	@echo "  install               Install Python dependencies"
	@echo "\n\033[1mDevelopment:\033[0m"
	@echo "  run                   Run the application"
	@echo "  test                  Run tests"
	@echo "  lint                  Run linting and code formatting"
	@echo "  cov                   Run tests with coverage report"
	@echo "\n\033[1mCV Tools:\033[0m"
	@echo "  convert-cv            Convert CV from Markdown to PDF (usage: make convert-cv INPUT=path/to/cv.md OUTPUT=path/to/output.pdf)"
	@echo "\n\033[1mDocker:\033[0m"
	@echo "  docker-build          Build Docker containers"
	@echo "  docker-up             Start all services"
	@echo "  docker-down           Stop all services"
	@echo "  docker-logs           View container logs"

# Setup virtual environment and install dependencies
.PHONY: setup
setup:
	@echo "\n\033[1m🚀 Setting up development environment...\033[0m"
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	$(PIP) install -r requirements-test.txt
	@echo "\n\033[1m✅ Setup complete! Activate virtual environment with:\033[0m\n\n  source $(VENV)/bin/activate\n"

# Install Python dependencies
.PHONY: install
install:
	$(PIP) install -r requirements.txt

# Run the application
.PHONY: run
run:
	cd $(CURDIR) && $(PYTHON) -m streamlit run app/main.py

# Run tests
.PHONY: test
test:
	$(PYTHON) -m pytest tests/ -v

# Run linting
.PHONY: lint
lint:
	@echo "\n\033[1m🔍 Running linters...\033[0m"
	$(PYTHON) -m flake8 app/ tests/
	$(PYTHON) -m black --check app/ tests/
	$(PYTHON) -m isort --check-only app/ tests/

# Run tests with coverage
.PHONY: cov
cov:
	$(PYTHON) -m pytest --cov=app --cov-report=term-missing --cov-report=html tests/

# Convert CV from Markdown to PDF
.PHONY: convert-cv
convert-cv:
	@if [ -z "$(INPUT)" ]; then \
		echo "Error: INPUT variable not set. Usage: make convert-cv INPUT=path/to/cv.md [OUTPUT=path/to/output.pdf]"; \
		exit 1; \
	fi
	$(PYTHON) scripts/convert_cv.py $(INPUT) $(OUTPUT)

# Docker commands
.PHONY: docker-build
docker-build:
	docker-compose build

.PHONY: docker-up
docker-up:
	docker-compose up -d

.PHONY: docker-down
docker-down:
	docker-compose down

.PHONY: docker-logs
docker-logs:
	docker-compose logs -f

# Clean up
.PHONY: clean
clean:
	find . -type d -name "__pycache__" -exec rm -r {} +
	find . -type d -name ".pytest_cache" -exec rm -r {} +
	rm -rf .coverage htmlcov/ .mypy_cache/ .pytest_cache/

# Help target for backward compatibility
.PHONY: all
all: help
