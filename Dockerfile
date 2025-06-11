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
COPY requirements.txt requirements-test.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt -r requirements-test.txt

# Download spaCy model
RUN python -m spacy download en_core_web_sm

# Copy application code
COPY . .

# Expose ports
EXPOSE 8501 8000

# Start command
CMD ["bash", "-c", "streamlit run app/main.py --server.port=8501 --server.address=0.0.0.0 & uvicorn app.api:app --host 0.0.0.0 --port 8000 & wait"]
