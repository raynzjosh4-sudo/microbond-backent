FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Cloud Run injects the PORT environment variable (defaults to 8080)
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
