import os

# Automatically configure Gunicorn to use Uvicorn ASGI workers for FastAPI
port = os.environ.get("PORT", "10000")
bind = f"0.0.0.0:{port}"
worker_class = "uvicorn.workers.UvicornWorker"
workers = int(os.environ.get("WEB_CONCURRENCY", "1"))
timeout = 120
keepalive = 5
