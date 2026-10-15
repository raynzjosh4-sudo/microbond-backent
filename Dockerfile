FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

WORKDIR /app

# Install dependencies in a separate layer
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy only application code (strictly respecting .dockerignore)
COPY . .

# Create and run as a non-privileged user for container security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Document ports supported: Local (8000), Cloud Run (8080), Render (10000)
EXPOSE 8000 8080 10000

# Universal runtime command: binds to $PORT provided by Render (10000), Cloud Run (8080), or Local (8000)
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
