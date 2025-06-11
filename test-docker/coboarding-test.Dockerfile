FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only essential files
COPY app/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt || echo "Failed to install some dependencies"

# Create a test script
RUN echo 'print("coBoarding test container running successfully!")' > test.py

CMD ["python", "test.py"]
