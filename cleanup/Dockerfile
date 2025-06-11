FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    cron \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /cleanup

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Setup cron job for daily cleanup
RUN echo "0 2 * * * /usr/local/bin/python /cleanup/daily_cleanup.py" | crontab -

CMD ["cron", "-f"]
