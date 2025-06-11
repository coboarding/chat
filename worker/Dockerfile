FROM python:3.11-slim

# Install system dependencies including Chrome
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    wget \
    gnupg \
    unzip \
    curl \
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Install ChromeDriver
RUN wget -O /tmp/chromedriver.zip https://chromedriver.storage.googleapis.com/114.0.5735.90/chromedriver_linux64.zip \
    && unzip /tmp/chromedriver.zip -d /opt/ \
    && rm /tmp/chromedriver.zip \
    && chmod +x /opt/chromedriver \
    && ln -fs /opt/chromedriver /usr/local/bin/chromedriver

WORKDIR /worker

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium

# Copy worker code
COPY . .

CMD ["python", "worker.py"]
