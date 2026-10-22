"""
Root entry point bridging uvicorn main:app and uvicorn app.main:app
Ensures compatibility with hosting environments that default to `main:app`.
"""
from app.main import app

__all__ = ["app"]
