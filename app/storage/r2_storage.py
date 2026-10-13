"""
r2_storage facade — redirects to app.services.storage.r2
"""
from app.services.storage.r2 import (
    get_r2_client,
    generate_presigned_url,
    upload_file_to_r2,
)

__all__ = [
    "get_r2_client",
    "generate_presigned_url",
    "upload_file_to_r2",
]
